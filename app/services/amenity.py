import re
import unicodedata
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityLog,
    Amenity,
    Establishment,
    EstablishmentAmenity,
    User,
)
from app.schemas.amenity import AmenityCreate, AmenityPatch


class AmenityService:

    @staticmethod
    async def get_amenity(
        amenity_id: UUID,
        session: AsyncSession,
    ) -> Amenity:
        result = await session.execute(
            select(Amenity).where(Amenity.id == amenity_id)
        )
        amenity = result.scalars().first()

        if amenity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Équipement introuvable.",
            )

        return amenity

    @staticmethod
    async def get_establishment(
        establishment_id: UUID,
        session: AsyncSession,
        *,
        for_update: bool = False,
    ) -> Establishment:
        statement = select(Establishment).where(
            Establishment.id == establishment_id
        )

        if for_update:
            statement = statement.with_for_update()

        result = await session.execute(statement)
        establishment = result.scalars().first()

        if establishment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Établissement introuvable.",
            )

        return establishment

   

    @staticmethod
    def audit(
        session: AsyncSession,
        actor: User,
        action: str,
        request: Request,
        *,
        amenity: Amenity | None = None,
        establishment_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        session.add(
            ActivityLog(
                user_id=actor.id,
                action=action,
                entity_type=(
                    "amenity"
                    if amenity
                    else "establishment_amenity"
                ),
                entity_id=(
                    amenity.id if amenity else establishment_id
                ),
                ip_address=(
                    request.client.host if request.client else None
                ),
                user_agent=(
                    request.headers.get("user-agent", "")[:1000]
                    or None
                ),
                metadata_json=metadata or {},
            )
        )

    @classmethod
    async def list_amenities(
        cls,
        session: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        count_result = await session.execute(
            select(func.count(Amenity.id))
        )

        result = await session.execute(
            select(Amenity)
            .order_by(Amenity.name, Amenity.id)
            .offset(offset)
            .limit(limit)
        )

        return {
            "items": result.scalars().all(),
            "total": count_result.scalar_one(),
            "limit": limit,
            "offset": offset,
        }

    @classmethod
    async def create_amenity(
        cls,
        data: AmenityCreate,
        request: Request,
        actor: User,
        session: AsyncSession,
    ) -> Amenity:
       
        amenity = Amenity(
            name=data.name,
            icon=data.icon,
        )

        session.add(amenity)

        try:
            await session.flush()

            cls.audit(
                session,
                actor,
                "ADMIN_AMENITY_CREATED",
                request,
                amenity=amenity,
            )

            await session.commit()
            await session.refresh(amenity)

        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de créer cet équipement : "
                "Une erreur s'est produite !",
            ) from exc

        return amenity

    @classmethod
    async def update_amenity(
        cls,
        amenity_id: UUID,
        data: AmenityPatch,
        request: Request,
        actor: User,
        session: AsyncSession,
    ) -> Amenity:
        amenity = await cls.get_amenity(amenity_id, session)

        changes = data.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(amenity, field, value)

        try:
            cls.audit(
                session,
                actor,
                "ADMIN_AMENITY_UPDATED",
                request,
                amenity=amenity,
            )

            await session.commit()
            await session.refresh(amenity)

        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de modifier cet équipement.",
            ) from exc

        return amenity

    @classmethod
    async def delete_amenity(
        cls,
        amenity_id: UUID,
        request: Request,
        actor: User,
        session: AsyncSession,
    ) -> dict:
        amenity = await cls.get_amenity(amenity_id, session)

        link_result = await session.execute(
            select(EstablishmentAmenity.establishment_id)
            .where(EstablishmentAmenity.amenity_id == amenity.id)
            .limit(1)
        )

        if link_result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Retirez d'abord cet équipement des "
                    "établissements qui l'utilisent."
                ),
            )

        cls.audit(
            session,
            actor,
            "ADMIN_AMENITY_DELETED",
            request,
            amenity=amenity,
        )

        await session.delete(amenity)

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet équipement ne peut pas être supprimé.",
            ) from exc

        return {"message": "Équipement supprimé."}

    @classmethod
    async def add_establishment_amenities(
        cls,
        establishment_id: UUID,
        data,
        request: Request,
        actor: User,
        session: AsyncSession,
    ) -> dict:
        establishment = await cls.get_establishment(
            establishment_id,
            session,
            for_update=True,
        )

        requested_ids = set(data.amenity_ids)

        if not requested_ids:
            return {
                "added_count": 0,
                "already_attached_count": 0,
            }

        amenity_result = await session.execute(
            select(Amenity.id).where(
                Amenity.id.in_(requested_ids)
            )
        )

        existing_amenity_ids = set(amenity_result.scalars().all())
        missing_ids = requested_ids - existing_amenity_ids

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Un ou plusieurs équipements n'existent pas."
                ),
            )

        existing_result = await session.execute(
            select(EstablishmentAmenity.amenity_id).where(
                EstablishmentAmenity.establishment_id
                == establishment.id,
                EstablishmentAmenity.amenity_id.in_(requested_ids),
            )
        )

        already_attached_ids = set(existing_result.scalars().all())
        new_ids = requested_ids - already_attached_ids

        for amenity_id in new_ids:
            session.add(
                EstablishmentAmenity(
                    establishment_id=establishment.id,
                    amenity_id=amenity_id,
                )
            )

        cls.audit(
            session,
            actor,
            "ADMIN_ESTABLISHMENT_AMENITIES_UPDATED",
            request,
            establishment_id=establishment.id,
            metadata={
                "added_ids": [str(item) for item in sorted(new_ids)],
                "requested_count": len(requested_ids),
            },
        )

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Les équipements ont changé pendant cette "
                    "requête ; recommencez."
                ),
            ) from exc

        return {
            "added_count": len(new_ids),
            "already_attached_count": len(already_attached_ids),
        }

    @classmethod
    async def remove_establishment_amenity(
        cls,
        establishment_id: UUID,
        amenity_id: UUID,
        request: Request,
        actor: User,
        session: AsyncSession,
    ) -> dict:
        establishment = await cls.get_establishment(
            establishment_id,
            session,
            for_update=True,
        )

        result = await session.execute(
            select(EstablishmentAmenity).where(
                EstablishmentAmenity.establishment_id
                == establishment.id,
                EstablishmentAmenity.amenity_id == amenity_id,
            )
        )

        link = result.scalars().first()

        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Cet équipement n'est pas associé à "
                    "l'établissement."
                ),
            )

        await session.delete(link)

        cls.audit(
            session,
            actor,
            "ADMIN_ESTABLISHMENT_AMENITY_REMOVED",
            request,
            establishment_id=establishment.id,
            metadata={"amenity_id": str(amenity_id)},
        )

        await session.commit()

        return {"message": "Équipement retiré de l'établissement."}
