from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import ActivityLog, Category, Establishment, SubCategory, User
from app.schemas.category import CategoryCreate, CategoryPatch


class CategoryService:

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
    ) -> Category:
        category = Category(name=data.name, icon=data.icon)
        session.add(category)
        await session.flush()
        self._audit(session, actor, "ADMIN_CATEGORY_CREATED", category, request)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de créer cette catégorie.",
            ) from exc
        await session.refresh(category)
        return category

    async def update(
        self,
        category_id: UUID,
        data: CategoryPatch,
        actor: User,
        request: Request,
        session: AsyncSession,
    ) -> Category:
        category = await self.get_or_404(category_id, session, for_update=True)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(category, field, value)
        self._audit(session, actor, "ADMIN_CATEGORY_UPDATED", category, request)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de mettre à jour cette catégorie.",
            ) from exc
        await session.refresh(category)
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

        return {"message": "Catégorie et sous-catégories associées supprimées."}    