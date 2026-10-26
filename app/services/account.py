from uuid import UUID

import httpx
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.helpers.cloudinary import (
    AVATAR_FOLDER,
    destroy_image,
    extract_public_id_from_url,
    upload_image,
)

from app.models import (
    ActivityLog,
    Favorite,
    Notification,
    Profile,
    Reservation,
    User,
)

from app.models.base import utc_now
from app.models.enums import UserProvider
from app.schemas.account import (
    AccountDeleteRequest,
    AccountProfilePatch,
    PasswordChangeRequest,
)
from app.services.oauth import OAuthService
from app.utils import generate_password_hash, verify_password

MAX_AVATAR_BYTES = 5 * 1024 * 1024


class AccountService:
    def __init__(self) -> None:
        self.oauth_service = OAuthService()


    @staticmethod
    def _profile_or_create(user: User, session: AsyncSession) -> Profile:
        if user.profile is None:
            user.profile = Profile(user_id=user.id)
            session.add(user.profile)
        return user.profile


    async def update_profile(
        self,
        user: User,
        data: AccountProfilePatch,
        session: AsyncSession,
    ) -> User:
        profile = self._profile_or_create(user, session)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)

        await session.commit()
        await session.refresh(user, ["profile"])
        return user

    async def delete_account(
        self,
        user: User,
        data: AccountDeleteRequest,
        session: AsyncSession,
    ) -> dict:

        if user.provider == UserProvider.LOCAL:
            if (
                not data.current_password
                or not user.password
                or not verify_password(data.current_password, user.password)
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Réauthentification invalide.",
                )
        else:
            if not data.provider_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Une réauthentification auprès du fournisseur est requise.",
                )

            try:
                if user.provider == UserProvider.GOOGLE:
                    identity = await self.oauth_service.verify_google_identity(
                        data.provider_token
                    )
                elif user.provider == UserProvider.FACEBOOK:
                    identity = await self.oauth_service.verify_facebook_identity(
                        data.provider_token
                    )
                else:
                    raise ValueError("Fournisseur de connexion non pris en charge.")

            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Réauthentification invalide.",
                ) from exc
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="La réauthentification du fournisseur est indisponible.",
                ) from exc
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Impossible de vérifier votre identité auprès du fournisseur.",
                ) from exc

            if identity["email"].casefold() != user.email.casefold():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Réauthentification invalide.",
                )

        deleted_email = f"deleted-{user.id}@deleted.invalid"

        reservation_result = await session.execute(
            select(Reservation).where(Reservation.user_id == user.id)
        )

        for reservation in reservation_result.scalars().all():
            reservation.client_first_name = "Compte"
            reservation.client_last_name = "supprimé"
            reservation.client_email = deleted_email
            reservation.client_phone = None

        await session.execute(
            delete(Favorite).where(Favorite.user_id == user.id)
        )
        await session.execute(
            delete(Notification).where(Notification.user_id == user.id)
        )
        await session.execute(
            delete(ActivityLog).where(ActivityLog.user_id == user.id)
        )

        profile = user.profile

        if profile and profile.img:
            public_id = extract_public_id_from_url(
                profile.img,
                expected_folder=AVATAR_FOLDER,
            )

            if public_id:
                try:
                    await destroy_image(
                        public_id,
                        expected_folder=AVATAR_FOLDER,
                    )
                except Exception:

                    pass

        if profile is not None:
            await session.delete(profile)

        user.is_deleted = True
        user.email = deleted_email
        user.password = None
     
        user.provider = UserProvider.LOCAL

        await session.commit()

        return {
            "message": "Compte supprimé avec succès. "
            "Les réservations historiques ont été conservées."
        }

    async def change_password(
        self,
        user: User,
        data: PasswordChangeRequest,
        session: AsyncSession,
    ) -> dict:
        if user.provider != UserProvider.LOCAL or not user.password:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le mot de passe de ce compte est géré par son fournisseur de connexion.",
            )

        if not verify_password(data.current_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Mot de passe actuel incorrect.",
            )

        user.password = generate_password_hash(data.new_password)
        user.token_version += 1
        await session.commit()
        return {"message": "Mot de passe modifié. Reconnectez-vous."}

    # ─── Avatar ───────────────────────────────────────────────────────────

    async def upload_avatar(
        self,
        user: User,
        avatar: UploadFile,
        session: AsyncSession,
    ) -> User:
        contents = await avatar.read(MAX_AVATAR_BYTES + 1)
        await avatar.close()

        if len(contents) > MAX_AVATAR_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="L'avatar ne peut pas dépasser 5 Mo.",
            )

        is_jpeg = contents.startswith(b"\xff\xd8\xff")
        is_png = contents.startswith(b"\x89PNG\r\n\x1a\n")
        is_webp = (
            len(contents) >= 12
            and contents.startswith(b"RIFF")
            and contents[8:12] == b"WEBP"
        )
        if not (is_jpeg or is_png or is_webp):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Formats acceptés : JPEG, PNG ou WebP.",
            )

        try:
            uploaded = await upload_image(
                contents,
                folder=AVATAR_FOLDER,
                allowed_formats=["jpg", "jpeg", "png", "webp"],
                transformation={"width": 512, "height": 512, "crop": "limit"},
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Le service de stockage d'images est indisponible.",
            ) from exc

        image_url = uploaded.get("secure_url")
        public_id = uploaded.get("public_id")

        if (
            not image_url
            or not public_id
            or not public_id.startswith(f"{AVATAR_FOLDER}/")
        ):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Le service de stockage a renvoyé une réponse invalide.",
            )

        profile = self._profile_or_create(user, session)

        # Supprimer l'ancien avatar (best-effort)
        old_public_id = extract_public_id_from_url(
            profile.img, expected_folder=AVATAR_FOLDER
        )
        if old_public_id and old_public_id != public_id:
            try:
                await destroy_image(old_public_id, expected_folder=AVATAR_FOLDER)
            except Exception:
                pass

        profile.img = image_url

        try:
            await session.commit()
            await session.refresh(user, ["profile"])
        except Exception:
            await session.rollback()
            try:
                await destroy_image(public_id, expected_folder=AVATAR_FOLDER)
            except Exception:
                pass
            raise

        return user

    async def delete_avatar(
        self,
        user: User,
        session: AsyncSession,
    ) -> User:
        profile = self._profile_or_create(user, session)

        public_id = extract_public_id_from_url(
            profile.img, expected_folder=AVATAR_FOLDER
        )
        if public_id:
            try:
                await destroy_image(public_id, expected_folder=AVATAR_FOLDER)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Impossible de supprimer l'avatar distant.",
                ) from exc

        profile.img = None
        await session.commit()
        await session.refresh(user, ["profile"])
        return user

    # ─── Notifications ────────────────────────────────────────────────────

    async def list_notifications(
        self,
        user: User,
        session: AsyncSession,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        statement = (
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(statement)
        return {
            "items": result.scalars().all(),
            "limit": limit,
            "offset": offset,
        }

    async def mark_notification_read(
        self,
        user: User,
        notification_id: UUID,
        session: AsyncSession,
    ) -> dict:
        result = await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user.id,
            )
        )
        notification = result.scalars().first()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification introuvable.",
            )

        notification.mark_as_read()
        await session.commit()
        return {"message": "Notification marquée comme lue."}

    async def mark_all_notifications_read(
        self,
        user: User,
        session: AsyncSession,
    ) -> dict:
        result = await session.execute(
            update(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=utc_now())
        )
        await session.commit()
        return {"updated_count": result.rowcount or 0}

    async def get_unread_count(
        self,
        user: User,
        session: AsyncSession,
    ) -> dict:
        result = await session.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        )
        return {"unread_count": result.scalar_one()}

    async def delete_notification(
        self,
        user: User,
        notification_id: UUID,
        session: AsyncSession,
    ) -> dict:
        result = await session.execute(
            delete(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user.id,
            )
        )
        if not result.rowcount:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification introuvable.",
            )
        await session.commit()
        return {"message": "Notification supprimée."}


 