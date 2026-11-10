import logging
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.helpers.cloudinary import (
    destroy_owner_document,
    owner_document_download_url,
    upload_owner_document,
)
from app.models import OwnerApplication, User
from app.models.base import utc_now
from app.models.enums import OwnerApplicationStatus, UserRole
from app.schemas.owners import (
    OwnerApplicationDecision,
    OwnerApplicationOwner,
    OwnerApplicationPublic,
)

logger = logging.getLogger(__name__)

class OwnerApplicationService:
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
    DOCUMENT_SIGNATURES = {
        ".pdf": ("application/pdf", b"%PDF-"),
        ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
        ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
        ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    }

    @classmethod
    async def _read_document(
        cls,
        file: UploadFile,
    ) -> tuple[bytes, str, str]:
        filename = Path(file.filename or "").name
        extension = Path(filename).suffix.lower()
        expected = cls.DOCUMENT_SIGNATURES.get(extension)
        if expected is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Format de document non pris en charge "
                    "(PDF, JPG ou PNG)."
                ),
            )

        contents = await file.read(cls.MAX_DOCUMENT_SIZE + 1)
        if not contents or len(contents) > cls.MAX_DOCUMENT_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Chaque document doit peser entre 1 octet et 10 Mo.",
            )

        expected_mime_type, signature = expected
        if (
            file.content_type != expected_mime_type
            or not contents.startswith(signature)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Le contenu du document ne correspond pas à son format.",
            )

        if len(filename) > 255:
            stem = Path(filename).stem
            filename = f"{stem[: 254 - len(extension)]}{extension}"
        return contents, filename, expected_mime_type

    @staticmethod
    def _to_public(
        application: OwnerApplication,
    ) -> OwnerApplicationPublic:
        return OwnerApplicationPublic(
            id=application.id,
            owner_id=application.owner_id,
            owner=OwnerApplicationOwner(
                id=application.owner.id,
                email=application.owner.email,
                firstName=(
                    application.owner.profile.firstName
                    if application.owner.profile
                    else None
                ),
                lastName=(
                    application.owner.profile.lastName
                    if application.owner.profile
                    else None
                ),
                phone=(
                    application.owner.profile.phone
                    if application.owner.profile
                    else None
                ),
                img=(
                    application.owner.profile.img
                    if application.owner.profile
                    else None
                ),
                city=(
                    application.owner.profile.city
                    if application.owner.profile
                    else None
                ),
            ),
            status=application.status,
            submitted_at=application.submitted_at,
            reviewed_at=application.reviewed_at,
            rejection_reason=application.rejection_reason,
            registry_document_url=owner_document_download_url(
                application.registry_file_public_id,
                application.registry_file_name,
            ),
            partnership_document_url=owner_document_download_url(
                application.partnership_file_public_id,
                application.partnership_file_name,
            ),
        )

    @staticmethod
    def _latest_application_query(owner_id: UUID):
        return (
            select(OwnerApplication)
            .options(
                selectinload(OwnerApplication.owner).selectinload(
                    User.profile
                )
            )
            .where(OwnerApplication.owner_id == owner_id)
            .order_by(
                OwnerApplication.submitted_at.desc(),
                OwnerApplication.id.desc(),
            )
            .limit(1)
        )

    async def is_approved(
        self,
        owner_id: UUID,
        session: AsyncSession,
    ) -> bool:
        result = await session.execute(
            select(OwnerApplication.id)
            .where(
                OwnerApplication.owner_id == owner_id,
                OwnerApplication.status == OwnerApplicationStatus.APPROUVE,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def submit(
        self,
        owner: User,
        registry_document: UploadFile,
        partnership_document: UploadFile,
        session: AsyncSession,
    ) -> OwnerApplicationPublic:
        previous_result = await session.execute(
            self._latest_application_query(owner.id)
        )
        previous = previous_result.scalars().first()
        if previous and previous.status != OwnerApplicationStatus.REJETE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Un dossier est déjà en cours de traitement ou a été "
                    "approuvé."
                ),
            )

        (
            registry_contents,
            registry_name,
            registry_mime,
        ) = await self._read_document(registry_document)
        (
            partnership_contents,
            partnership_name,
            partnership_mime,
        ) = await self._read_document(partnership_document)

        uploaded_public_ids: list[str] = []
        try:
            registry_upload = await upload_owner_document(registry_contents)
            registry_public_id = registry_upload["public_id"]
            uploaded_public_ids.append(registry_public_id)

            partnership_upload = await upload_owner_document(
                partnership_contents
            )
            partnership_public_id = partnership_upload["public_id"]
            uploaded_public_ids.append(partnership_public_id)

            await session.execute(
                select(User.id).where(User.id == owner.id).with_for_update()
            )
            latest_result = await session.execute(
                self._latest_application_query(owner.id)
            )
            latest = latest_result.scalars().first()
            if latest and latest.status != OwnerApplicationStatus.REJETE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Un dossier est déjà en cours de traitement ou a été "
                        "approuvé."
                    ),
                )

            application = OwnerApplication(
                owner_id=owner.id,
                status=OwnerApplicationStatus.EN_ATTENTE,
                registry_file_name=registry_name,
                registry_file_public_id=registry_public_id,
                registry_mime_type=registry_mime,
                registry_file_size=len(registry_contents),
                partnership_file_name=partnership_name,
                partnership_file_public_id=partnership_public_id,
                partnership_mime_type=partnership_mime,
                partnership_file_size=len(partnership_contents),
            )
            session.add(application)
            await session.commit()
            application_result = await session.execute(
                select(OwnerApplication)
                .options(
                    selectinload(OwnerApplication.owner).selectinload(
                        User.profile
                    )
                )
                .where(OwnerApplication.id == application.id)
            )
            application = application_result.scalars().one()
            return self._to_public(application)
        except Exception:
            await session.rollback()
            for public_id in uploaded_public_ids:
                try:
                    await destroy_owner_document(public_id)
                except Exception:
                    logger.exception(
                        "Failed to clean up uploaded owner document %s",
                        public_id,
                    )
            raise

    async def get_latest(
        self,
        owner_id: UUID,
        session: AsyncSession,
    ) -> OwnerApplicationPublic:
        result = await session.execute(
            self._latest_application_query(owner_id)
        )
        application = result.scalars().first()
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aucun dossier propriétaire n'a été soumis.",
            )
        return self._to_public(application)

    async def list_applications(
        self,
        session: AsyncSession,
        *,
        application_status: OwnerApplicationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[OwnerApplicationPublic]:
        statement = select(OwnerApplication).options(
            selectinload(OwnerApplication.owner).selectinload(User.profile)
        ).join(User, User.id == OwnerApplication.owner_id).where(
            User.role == UserRole.PROPRIETAIRE,
            User.is_deleted.is_(False),
        )
        if application_status is not None:
            statement = statement.where(
                OwnerApplication.status == application_status
            )
        result = await session.execute(
            statement
            .order_by(
                OwnerApplication.submitted_at.desc(),
                OwnerApplication.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return [
            self._to_public(application)
            for application in result.scalars().all()
        ]

    async def get_application(
        self,
        application_id: UUID,
        session: AsyncSession,
    ) -> OwnerApplicationPublic:
        result = await session.execute(
            select(OwnerApplication)
            .options(
                selectinload(OwnerApplication.owner).selectinload(
                    User.profile
                )
            )
            .join(User, User.id == OwnerApplication.owner_id)
            .where(
                OwnerApplication.id == application_id,
                User.role == UserRole.PROPRIETAIRE,
                User.is_deleted.is_(False),
            )
        )
        application = result.scalars().first()
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dossier propriétaire introuvable.",
            )
        return self._to_public(application)

    async def review(
        self,
        application_id: UUID,
        decision: OwnerApplicationDecision,
        reviewer: User,
        session: AsyncSession,
    ) -> OwnerApplicationPublic:
        result = await session.execute(
            select(OwnerApplication)
            .options(
                selectinload(OwnerApplication.owner).selectinload(
                    User.profile
                )
            )
            .where(OwnerApplication.id == application_id)
            .with_for_update()
        )
        application = result.scalars().first()
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dossier propriétaire introuvable.",
            )
        if (
            application.owner.role != UserRole.PROPRIETAIRE
            or application.owner.is_deleted
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le compte associé à ce dossier n'est plus valide.",
            )
        if application.status != OwnerApplicationStatus.EN_ATTENTE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce dossier a déjà été traité.",
            )

        application.status = OwnerApplicationStatus(decision.decision)
        application.reviewed_by = reviewer.id
        application.reviewed_at = utc_now()
        application.rejection_reason = (
            decision.rejection_reason
            if application.status == OwnerApplicationStatus.REJETE
            else None
        )
        await session.commit()
        await session.refresh(application)
        logger.info(
            "Owner application %s reviewed as %s by %s at %s",
            application.id,
            application.status.value,
            reviewer.id,
            application.reviewed_at.isoformat(),
        )
        return self._to_public(application)


owner_application_service = OwnerApplicationService()
