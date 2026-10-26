from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import ActivityLog, Category, Establishment, SubCategory, User
from app.schemas.subcategory import SubcategoryCreate, SubcategoryPatch
from app.services.category import CategoryService


category_service = CategoryService()

class SubcategoryService:

    @staticmethod
    async def get_or_404(
        subcategory_id: UUID,
        session: AsyncSession,
        *,
        for_update: bool = False,
    ) -> SubCategory:
        statement = select(SubCategory).where(
            SubCategory.id == subcategory_id,
            SubCategory.id.isnot(None),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await session.execute(statement)
        subcategory = result.scalars().first()
        if not subcategory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sous-catégorie introuvable.",
            )
        return subcategory

    @staticmethod
    def _audit(
        session: AsyncSession,
        actor: User,
        action: str,
        entity: SubCategory,
        request: Request,
    ) -> None:
        session.add(
            ActivityLog(
                user_id=actor.id,
                action=action,
                entity_type="subcategory",
                entity_id=entity.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:1000] or None,
            )
        )

    async def list(
        self,
        session: AsyncSession,
        *,
        category_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        filters = [
            SubCategory.id.isnot(None),
            Category.id.isnot(None),
        ]
        if category_id is not None:
            filters.append(SubCategory.category_id == category_id)

        count_result = await session.execute(
            select(func.count(SubCategory.id))
            .join(Category, Category.id == SubCategory.category_id)
            .where(*filters)
        )
        result = await session.execute(
            select(SubCategory)
            .join(Category, Category.id == SubCategory.category_id)
            .where(*filters)
            .order_by(SubCategory.name, SubCategory.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": result.scalars().all(),
            "total": count_result.scalar_one(),
            "limit": limit,
            "offset": offset,
        }

    async def list_by_category(
        self,
        category_id: UUID,
        session: AsyncSession,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        await category_service.get_or_404(category_id, session)
        return await self.list(
            session,
            category_id=category_id,
            limit=limit,
            offset=offset,
        )

    async def get_by_id(
        self,
        subcategory_id: UUID,
        session: AsyncSession,
    ) -> SubCategory:
        return await self.get_or_404(subcategory_id, session)

    async def create(
        self,
        category_id: UUID,
        data: SubcategoryCreate,
        actor: User,
        request: Request,
        session: AsyncSession,
    ) -> SubCategory:
        await category_service.get_or_404(category_id, session, for_update=True)

        subcategory = SubCategory(
            category_id=category_id,
            name=data.name,
            icon=data.icon,
        )
        session.add(subcategory)
        await session.flush()
        self._audit(session, actor, "ADMIN_SUBCATEGORY_CREATED", subcategory, request)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de créer cette sous-catégorie.",
            ) from exc
        await session.refresh(subcategory)
        return subcategory

    async def update(
        self,
        subcategory_id: UUID,
        data: SubcategoryPatch,
        actor: User,
        request: Request,
        session: AsyncSession,
    ) -> SubCategory:
        subcategory = await self.get_or_404(
            subcategory_id, session, for_update=True
        )
        changes = data.model_dump(exclude_unset=True)
        new_category_id = changes.get("category_id", subcategory.category_id)

        # Vérifier que la catégorie cible existe
        await category_service.get_or_404(
            new_category_id, session, for_update=True
        )

        # Interdire le déplacement si des établissements actifs l'utilisent
        if new_category_id != subcategory.category_id:
            establishment_result = await session.execute(
                select(Establishment.id)
                .where(
                    Establishment.subcategory_id == subcategory.id,
                    Establishment.deleted_at.is_(None),
                )
                .limit(1)
            )
            if establishment_result.first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Une sous-catégorie utilisée ne peut pas être déplacée.",
                )

        for field, value in changes.items():
            setattr(subcategory, field, value)

        self._audit(session, actor, "ADMIN_SUBCATEGORY_UPDATED", subcategory, request)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de mettre à jour cette sous-catégorie.",
            ) from exc
        await session.refresh(subcategory)
        return subcategory

    async def delete(
        self,
        subcategory_id: UUID,
        actor: User,
        request: Request,
        session: AsyncSession,
    ) -> dict:
        subcategory = await self.get_or_404(
            subcategory_id, session, for_update=True
        )

        self._audit(session, actor, "ADMIN_SUBCATEGORY_DELETED", subcategory, request)
        await session.delete(subcategory)

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de supprimer : des établissements y sont encore liés.",
        ) from exc

        return {"message": "Sous-catégorie supprimée."}