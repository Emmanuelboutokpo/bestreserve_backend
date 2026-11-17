import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.helpers.cloudinary import (
    destroy_image,
    extract_public_id_from_url,
    upload_image,
)
from app.models import ActivityLog, Category, Establishment, SubCategory, User
from app.schemas.category import CategoryCreate, CategoryPatch


logger = logging.getLogger(__name__)


class CategoryService:
    CATEGORY_IMAGE_FOLDER = "bestreserv/categories"
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    IMAGE_SIGNATURES = {
        "image/jpeg": b"\xff\xd8\xff",
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/webp": None,
    }

    @classmethod
    async def _read_image(cls, image: UploadFile) -> bytes:
        content_type = image.content_type or ""
        if content_type not in cls.IMAGE_SIGNATURES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Formats acceptés : JPEG, PNG ou WebP.",
            )

        contents = await image.read(cls.MAX_IMAGE_BYTES + 1)
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Le fichier image est vide.",
            )
        if len(contents) > cls.MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="L'image ne peut pas dépasser 5 Mo.",
            )

        signature = cls.IMAGE_SIGNATURES[content_type]
        is_webp = (
            content_type == "image/webp"
            and len(contents) >= 12
            and contents.startswith(b"RIFF")
            and contents[8:12] == b"WEBP"
        )
        if (signature is not None and not contents.startswith(signature)) or (
            content_type == "image/webp" and not is_webp
        ):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Le contenu du fichier ne correspond pas à son format.",
            )
        return contents

    @classmethod
    async def _upload_category_image(
        cls,
        contents: bytes,
    ) -> dict[str, Any]:
        try:
            uploaded = await upload_image(
                contents,
                folder=cls.CATEGORY_IMAGE_FOLDER,
                allowed_formats=["jpg", "jpeg", "png", "webp"],
                transformation={
                    "width": 800,
                    "height": 800,
                    "crop": "limit",
                },
            )
        except Exception as exc:
            logger.exception("Category image upload failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Le service de stockage d'images est indisponible.",
            ) from exc

        if not isinstance(uploaded, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Le service de stockage a renvoyé une réponse invalide.",
            )

        image_url = uploaded.get("secure_url")
        public_id = uploaded.get("public_id")
        if (
            not image_url
            or not public_id
            or not public_id.startswith(f"{cls.CATEGORY_IMAGE_FOLDER}/")
        ):
            if public_id and public_id.startswith(
                f"{cls.CATEGORY_IMAGE_FOLDER}/"
            ):
                try:
                    await destroy_image(
                        public_id,
                        expected_folder=cls.CATEGORY_IMAGE_FOLDER,
                    )
                except Exception:
                    logger.exception(
                        "Could not clean up invalid category image upload"
                    )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Le service de stockage a renvoyé une réponse invalide.",
            )
        return uploaded

    @classmethod
    async def _destroy_category_image(cls, image_url: str | None) -> None:
        public_id = extract_public_id_from_url(
            image_url,
            expected_folder=cls.CATEGORY_IMAGE_FOLDER,
        )
        if public_id:
            await destroy_image(
                public_id,
                expected_folder=cls.CATEGORY_IMAGE_FOLDER,
            )

    @classmethod
    async def _cleanup_uploaded_image(cls, public_id: str) -> None:
        try:
            await destroy_image(
                public_id,
                expected_folder=cls.CATEGORY_IMAGE_FOLDER,
            )
        except Exception:
            logger.exception("Could not clean up category image %s", public_id)

    @classmethod
    async def _cleanup_replaced_image(cls, image_url: str | None) -> None:
        try:
            await cls._destroy_category_image(image_url)
        except Exception:
            logger.exception("Could not remove replaced category image")

    @staticmethod
    async def get_or_404(
        category_id: UUID,
        session: AsyncSession,
        *,
        for_update: bool = False,
    ) -> Category:
        statement = select(Category).where(
            Category.id == category_id,
            Category.id.isnot(None),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await session.execute(statement)
        category = result.scalars().first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Catégorie introuvable.",
            )
        return category

    @staticmethod
    def _audit(
        session: AsyncSession,
        actor: User,
        action: str,
        entity: Category,
        request: Request,
    ) -> None:
        session.add(
            ActivityLog(
                user_id=actor.id,
                action=action,
                entity_type="category",
                entity_id=entity.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:1000] or None,
            )
        )

    async def list(
        self,
        session: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        filters = [Category.id.isnot(None)]
        count_result = await session.execute(
            select(func.count(Category.id)).where(*filters)
        )
        result = await session.execute(
            select(Category)
            .where(*filters)
            .order_by(Category.name, Category.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": result.scalars().all(),
            "total": count_result.scalar_one(),
            "limit": limit,
            "offset": offset,
        }

    async def get_by_id(
        self,
        category_id: UUID,
        session: AsyncSession,
    ) -> Category:
        return await self.get_or_404(category_id, session)

    async def create(
        self,
        data: CategoryCreate,
        actor: User,
        request: Request,
        session: AsyncSession,
        *,
        image: UploadFile | None = None,
    ) -> Category:
        uploaded = None
        if image is not None:
            contents = await self._read_image(image)
            uploaded = await self._upload_category_image(contents)

        category = Category(
            name=data.name,
            icon=data.icon,
            img=uploaded["secure_url"] if uploaded else None,
        )
        session.add(category)
        try:
            await session.flush()
            self._audit(
                session,
                actor,
                "ADMIN_CATEGORY_CREATED",
                category,
                request,
            )
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            if uploaded:
                await self._cleanup_uploaded_image(uploaded["public_id"])
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de créer cette catégorie.",
            ) from exc
        except Exception:
            await session.rollback()
            if uploaded:
                await self._cleanup_uploaded_image(uploaded["public_id"])
            raise
        await session.refresh(category)
        return category

    async def update(
        self,
        category_id: UUID,
        data: CategoryPatch,
        actor: User,
        request: Request,
        session: AsyncSession,
        *,
        image: UploadFile | None = None,
    ) -> Category:
        category = await self.get_or_404(category_id, session, for_update=True)
        changes = data.model_dump(exclude_unset=True)
        if not changes and image is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Fournissez des champs à modifier ou une nouvelle image.",
            )
        for field, value in changes.items():
            setattr(category, field, value)
        uploaded = None
        old_image_url = category.img
        if image is not None:
            contents = await self._read_image(image)
            uploaded = await self._upload_category_image(contents)
            category.img = uploaded["secure_url"]

        self._audit(session, actor, "ADMIN_CATEGORY_UPDATED", category, request)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            if uploaded:
                await self._cleanup_uploaded_image(uploaded["public_id"])
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de mettre à jour cette catégorie.",
            ) from exc
        except Exception:
            await session.rollback()
            if uploaded:
                await self._cleanup_uploaded_image(uploaded["public_id"])
            raise
        await session.refresh(category)
        if uploaded:
            await self._cleanup_replaced_image(old_image_url)
        return category

    async def delete_image(
        self,
        category_id: UUID,
        actor: User,
        request: Request,
        session: AsyncSession,
    ) -> Category:
        category = await self.get_or_404(category_id, session, for_update=True)
        old_image_url = category.img
        category.img = None
        self._audit(
            session,
            actor,
            "ADMIN_CATEGORY_IMAGE_DELETED",
            category,
            request,
        )
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        await session.refresh(category)
        await self._cleanup_replaced_image(old_image_url)
        return category

    async def delete(
        self,
        category_id: UUID,
        actor: User,
        request: Request,
        session: AsyncSession,
    ) -> dict:
        category = await self.get_or_404(category_id, session, for_update=True)

    # Supprimer toutes les sous-catégories liées
        subcategories_result = await session.execute(
            select(SubCategory).where(SubCategory.category_id == category.id)
        )
        for subcategory in subcategories_result.scalars().all():
            self._audit(
                session, actor, "ADMIN_SUBCATEGORY_DELETED", subcategory, request
            )
            await session.delete(subcategory)

        self._audit(session, actor, "ADMIN_CATEGORY_DELETED", category, request)
        await session.delete(category)

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de supprimer : des établissements sont encore liés à cette catégorie ou ses sous-catégories.",
        ) from exc

        await self._cleanup_replaced_image(category.img)
        return {"message": "Catégorie et sous-catégories associées supprimées."}     