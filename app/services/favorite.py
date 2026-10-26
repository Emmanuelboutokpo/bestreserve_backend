from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Category,
    Establishment,
    Favorite,
    Location,
    SubCategory,
)
from app.models.enums import EstablishmentStatus


class FavoriteService:

    # ---------------------------------------------------------
    # REQUÊTE COMMUNE : FAVORIS D'UN UTILISATEUR
    # ---------------------------------------------------------

    @staticmethod
    def _favorite_query(user_id: UUID):
        return (
            select(Favorite)
            .join(
                Establishment,
                Establishment.id == Favorite.establishment_id,
            )
            .join(
                Category,
                Category.id == Establishment.category_id,
            )
            .outerjoin(
                SubCategory,
                SubCategory.id == Establishment.subcategory_id,
            )
            .join(
                Location,
                Location.id == Establishment.location_id,
            )
            .options(
                selectinload(Favorite.establishment)
            )
            .where(
                Favorite.user_id == user_id,
                Establishment.status == EstablishmentStatus.PUBLIE,
                Location.is_active.is_(True),
            )
        )

    # ---------------------------------------------------------
    # VÉRIFIER L'ACCESSIBILITÉ PUBLIQUE D'UN ÉTABLISSEMENT
    # ---------------------------------------------------------

    @staticmethod
    async def public_establishment_exists(
        establishment_id: UUID,
        session: AsyncSession,
    ) -> bool:
        result = await session.execute(
            select(Establishment.id)
            .join(
                Category,
                Category.id == Establishment.category_id,
            )
            .outerjoin(
                SubCategory,
                SubCategory.id == Establishment.subcategory_id,
            )
            .join(
                Location,
                Location.id == Establishment.location_id,
            )
            .where(
                Establishment.id == establishment_id,
                Establishment.status == EstablishmentStatus.PUBLIE,
                Location.is_active.is_(True),
            )
        )

        return result.first() is not None

    # ---------------------------------------------------------
    # LISTER LES FAVORIS
    # ---------------------------------------------------------

    @classmethod
    async def list_my_favorites(
        cls,
        user_id: UUID,
        session: AsyncSession,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        query = cls._favorite_query(user_id)

        count_query = (
            select(func.count(func.distinct(Favorite.id)))
            .join(
                Establishment,
                Establishment.id == Favorite.establishment_id,
            )
            .join(
                Category,
                Category.id == Establishment.category_id,
            )
            .outerjoin(
                SubCategory,
                SubCategory.id == Establishment.subcategory_id,
            )
            .join(
                Location,
                Location.id == Establishment.location_id,
            )
            .where(
                Favorite.user_id == user_id,
                Establishment.status == EstablishmentStatus.PUBLIE,
                Location.is_active.is_(True),
            )
        )

        count_result = await session.execute(count_query)

        result = await session.execute(
            query
            .order_by(
                Favorite.created_at.desc(),
                Favorite.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return {
            "items": result.scalars().all(),
            "total": count_result.scalar_one(),
            "limit": limit,
            "offset": offset,
        }

    # ---------------------------------------------------------
    # AJOUTER UN FAVORI
    # ---------------------------------------------------------

    @classmethod
    async def add_favorite(
        cls,
        user_id: UUID,
        establishment_id: UUID,
        session: AsyncSession,
    ) -> dict:
        is_public = await cls.public_establishment_exists(
            establishment_id,
            session,
        )

        if not is_public:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Établissement introuvable.",
            )

        existing = await session.execute(
            select(Favorite.id).where(
                Favorite.user_id == user_id,
                Favorite.establishment_id == establishment_id,
            )
        )

        if existing.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet établissement est déjà dans vos favoris.",
            )

        favorite = Favorite(
            user_id=user_id,
            establishment_id=establishment_id,
        )

        session.add(favorite)

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible d'ajouter ce favori : "
                "il existe peut-être déjà.",
            ) from exc

        return {
            "message": "Établissement ajouté aux favoris."
        }

    # ---------------------------------------------------------
    # RETIRER UN FAVORI
    # ---------------------------------------------------------

    @staticmethod
    async def remove_favorite(
        user_id: UUID,
        establishment_id: UUID,
        session: AsyncSession,
    ) -> dict:
        result = await session.execute(
            delete(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.establishment_id == establishment_id,
            )
        )

        if not result.rowcount:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favori introuvable.",
            )

        await session.commit()

        return {
            "message": "Établissement retiré des favoris."
        }

    # ---------------------------------------------------------
    # VIDER LES FAVORIS
    # ---------------------------------------------------------

    @staticmethod
    async def clear_my_favorites(
        user_id: UUID,
        session: AsyncSession,
    ) -> dict:
        result = await session.execute(
            delete(Favorite).where(
                Favorite.user_id == user_id
            )
        )

        deleted_count = result.rowcount or 0

        await session.commit()

        return {
            "deleted_count": deleted_count
        }
 