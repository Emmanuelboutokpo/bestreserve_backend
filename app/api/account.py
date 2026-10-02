import cloudinary
import httpx
from uuid import UUID
from cloudinary import uploader
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, inspect, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.cores.db import get_session
from app.dependencies.dependencies import (
    get_current_user,
    require_client,
)
from app.models import (
    ActivityLog,
    Favorite,
    Notification,
    Profile,
    Reservation,
    Review,
    Transaction,
    User,
    UserConsent,
)
from app.models.base import utc_now
from app.models.enums import UserProvider, UserStatus
from app.schemas.account import (
    AccountDeleteRequest,
    AccountProfilePatch,
    ConsentUpdateRequest,
    NotificationPage,
    PasswordChangeRequest,
)
from app.schemas.auth import UserPublic
from app.services.oauth import OAuthService
from app.utils import generate_password_hash, verify_password


account_router = APIRouter(
    tags=["Compte client"],
    dependencies=[Depends(require_client)],
)
oauth_service = OAuthService()
MAX_AVATAR_BYTES = 5 * 1024 * 1024
CONSENT_PURPOSES = (
    "marketing_email",
    "marketing_sms",
    "analytics",
    "personalization",
)


def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


async def _destroy_avatar(public_id: str | None) -> None:
    if not public_id:
        return
    if not public_id.startswith("bestrev/avatars/"):
        raise ValueError("Identifiant d'avatar invalide.")

    _configure_cloudinary()
    await run_in_threadpool(
        uploader.destroy,
        public_id,
        resource_type="image",
        invalidate=True,
    )


def _profile_or_create(user: User, session: AsyncSession) -> Profile:
    if user.profile is None:
        user.profile = Profile(user_id=user.id)
        session.add(user.profile)
    return user.profile


@account_router.get("/users/me", response_model=UserPublic)
async def get_my_account(
    current_user: User = Depends(get_current_user),
):
    return current_user


@account_router.patch("/users/me", response_model=UserPublic)
async def update_my_account(
    data: AccountProfilePatch,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = _profile_or_create(current_user, session)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await session.commit()
    await session.refresh(current_user, ["profile"])
    return current_user


@account_router.delete("/users/me")
async def delete_my_account(
    data: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.provider == UserProvider.LOCAL:
        if (
            not data.current_password
            or not current_user.password
            or not verify_password(data.current_password, current_user.password)
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
            if current_user.provider == UserProvider.GOOGLE:
                identity = await oauth_service.verify_google_identity(
                    data.provider_token
                )
            elif current_user.provider == UserProvider.FACEBOOK:
                identity = await oauth_service.verify_facebook_identity(
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

        if identity["email"].casefold() != current_user.email.casefold():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Réauthentification invalide.",
            )

    profile = _profile_or_create(current_user, session)
    try:
        await _destroy_avatar(profile.avatar_public_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de supprimer l'avatar distant.",
        ) from exc

    deleted_email = f"deleted-{current_user.id}@deleted.invalid"
    reservation_result = await session.execute(
        select(Reservation).where(Reservation.user_id == current_user.id)
    )
    for reservation in reservation_result.scalars().all():
        reservation.client_first_name = "Compte"
        reservation.client_last_name = "supprimé"
        reservation.client_email = deleted_email
        reservation.client_phone = None

    await session.execute(
        delete(Favorite).where(Favorite.user_id == current_user.id)
    )
    await session.execute(
        delete(Notification).where(Notification.user_id == current_user.id)
    )
    await session.execute(
        delete(UserConsent).where(UserConsent.user_id == current_user.id)
    )
    await session.execute(
        delete(ActivityLog).where(ActivityLog.user_id == current_user.id)
    )

    profile.firstName = None
    profile.lastName = None
    profile.phone = None
    profile.img = None
    profile.avatar_public_id = None
    profile.bio = None
    profile.country_code = None
    profile.city = None

    current_user.email = deleted_email
    current_user.password = None
    current_user.refreshToken = None
    current_user.status = UserStatus.INACTIF
    current_user.deleted_at = utc_now()
    current_user.token_version += 1

    await session.commit()
    return {"message": "Compte supprimé et données personnelles anonymisées."}


@account_router.put("/users/me/password")
async def change_my_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.provider != UserProvider.LOCAL or not current_user.password:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le mot de passe de ce compte est géré par son fournisseur de connexion.",
        )

    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe actuel incorrect.",
        )

    current_user.password = generate_password_hash(data.new_password)
    current_user.token_version += 1
    await session.commit()

    return {"message": "Mot de passe modifié. Reconnectez-vous."}


@account_router.post("/users/me/avatar", response_model=UserPublic)
async def upload_my_avatar(
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
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

    _configure_cloudinary()
    try:
        uploaded = await run_in_threadpool(
            uploader.upload,
            contents,
            folder="bestrev/avatars",
            resource_type="image",
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
    if not image_url or not public_id or not public_id.startswith("bestrev/avatars/"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le service de stockage a renvoyé une réponse invalide.",
        )

    profile = _profile_or_create(current_user, session)
    previous_public_id = profile.avatar_public_id
    profile.img = image_url
    profile.avatar_public_id = public_id
    try:
        await session.commit()
        await session.refresh(current_user, ["profile"])
    except Exception:
        await session.rollback()
        try:
            await _destroy_avatar(public_id)
        except Exception:
            pass
        raise

    if previous_public_id and previous_public_id != public_id:
        try:
            await _destroy_avatar(previous_public_id)
        except Exception:
            pass
    return current_user


@account_router.delete("/users/me/avatar", response_model=UserPublic)
async def delete_my_avatar(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = _profile_or_create(current_user, session)
    try:
        await _destroy_avatar(profile.avatar_public_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de supprimer l'avatar distant.",
        ) from exc

    profile.img = None
    profile.avatar_public_id = None
    await session.commit()
    await session.refresh(current_user, ["profile"])
    return current_user


@account_router.get("/users/me/notifications", response_model=NotificationPage)
async def list_my_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(statement)
    return {"items": result.scalars().all(), "limit": limit, "offset": offset}


@account_router.patch("/users/me/notifications/{notification_id}/read")
async def mark_my_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
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


@account_router.patch("/users/me/notifications/read-all")
async def mark_all_my_notifications_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=utc_now())
    )
    await session.commit()
    return {"updated_count": result.rowcount or 0}


@account_router.get("/users/me/export")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    def serialize(record) -> dict:
        return {
            attribute.key: getattr(record, attribute.key)
            for attribute in inspect(record).mapper.column_attrs
        }

    consent_result = await session.execute(
        select(UserConsent).where(UserConsent.user_id == current_user.id)
    )
    consent_rows = consent_result.scalars().all()
    user_data = {
        "account": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role,
            "status": current_user.status,
            "provider": current_user.provider,
            "created_at": current_user.created_at,
        },
        "profile": serialize(current_user.profile) if current_user.profile else None,
        "consents": [serialize(row) for row in consent_rows],
    }

    for key, model in (
        ("activity_logs", ActivityLog),
        ("favorites", Favorite),
        ("notifications", Notification),
        ("reservations", Reservation),
        ("reviews", Review),
        ("transactions", Transaction),
    ):
        result = await session.execute(
            select(model).where(model.user_id == current_user.id)
        )
        user_data[key] = [serialize(row) for row in result.scalars().all()]

    return jsonable_encoder(user_data)


@account_router.get("/users/me/consents")
async def get_my_consents(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserConsent).where(UserConsent.user_id == current_user.id)
    )
    saved = {row.purpose: row.granted for row in result.scalars().all()}
    return {purpose: saved.get(purpose, False) for purpose in CONSENT_PURPOSES}


@account_router.put("/users/me/consents")
async def update_my_consents(
    data: ConsentUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    changes = data.model_dump(exclude_unset=True)
    result = await session.execute(
        select(UserConsent).where(
            UserConsent.user_id == current_user.id,
            UserConsent.purpose.in_(changes),
        )
    )
    saved = {row.purpose: row for row in result.scalars().all()}

    for purpose, granted in changes.items():
        consent = saved.get(purpose)
        if consent is None:
            consent = UserConsent(
                user_id=current_user.id,
                purpose=purpose,
                granted=granted,
            )
            session.add(consent)
            consent.granted_at = utc_now() if granted else None
        else:
            was_granted = consent.granted
            consent.granted = granted
            if not granted:
                consent.granted_at = None
            elif not was_granted:
                consent.granted_at = utc_now()

    await session.commit()
    return await get_my_consents(current_user, session)