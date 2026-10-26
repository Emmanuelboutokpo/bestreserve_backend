import re
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import (
    ActivityLog,
    Amenity,
    Establishment,
    EstablishmentAmenity,
    User,
)
from app.models.base import utc_now
from app.schemas.amenity import (
    AmenityCreate,
    AmenityPage,
    AmenityPatch,
    AmenityPublic,
    EstablishmentAmenityRequest,
)


amenities_router = APIRouter(prefix="/amenities", tags=["Équipements"])

admin_amenities_router = APIRouter(
    prefix="/admin/amenities",
    tags=["Administration des équipements"],
    dependencies=[Depends(require_admin)],
)

admin_establishment_amenities_router = APIRouter(
    prefix="/admin/establishments",
    tags=["Équipements des établissements"],
    dependencies=[Depends(require_admin)],
)


async def _get_amenity(amenity_id: UUID, session: AsyncSession) -> Amenity:
    result = await session.execute(
        select(Amenity).where(
            Amenity.id == amenity_id,
            Amenity.id.isnot(None),
        )
    )
    amenity = result.scalars().first()
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Équipement introuvable.",
        )
    return amenity


async def _get_establishment(
    establishment_id: UUID,
    session: AsyncSession,
    *,
    for_update: bool = False,
) -> Establishment:
    statement = select(Establishment).where(
        Establishment.id == establishment_id,
        Establishment.id.isnot(None),
    )
    if for_update:
        statement = statement.with_for_update()
    result = await session.execute(statement)
    establishment = result.scalars().first()
    if not establishment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Établissement introuvable.",
        )
    return establishment


def _audit(
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
            entity_type="amenity" if amenity else "establishment_amenity",
            entity_id=amenity.id if amenity else establishment_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:1000] or None,
            metadata_json=metadata or {},
        )
    )


@amenities_router.get("", response_model=AmenityPage)
async def list_amenities(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    filters = [Amenity.id.isnot(None)]
    count_result = await session.execute(
        select(func.count(Amenity.id)).where(*filters)
    )
    result = await session.execute(
        select(Amenity)
        .where(*filters)
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


@admin_amenities_router.post(
    "",
    response_model=AmenityPublic,
    status_code=status.HTTP_201_CREATED,
)

async def create_amenity(
    data: AmenityCreate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    amenity = Amenity(name=data.name, icon=data.icon)
    session.add(amenity)
    await session.flush()
    _audit(session, actor, "ADMIN_AMENITY_CREATED", request, amenity=amenity)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce slug d'équipement est déjà utilisé.",
        ) from exc
    await session.refresh(amenity)
    return amenity


@admin_amenities_router.patch("/{amenity_id}", response_model=AmenityPublic)
async def update_amenity(
    amenity_id: UUID,
    data: AmenityPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    amenity = await _get_amenity(amenity_id, session)
    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(amenity, field, value)
    _audit(session, actor, "ADMIN_AMENITY_UPDATED", request, amenity=amenity)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une erreur s'est  produite !",
        ) from exc
    await session.refresh(amenity)
    return amenity


@admin_amenities_router.delete("/{amenity_id}")
async def delete_amenity(
    amenity_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    amenity = await _get_amenity(amenity_id, session)

    link_result = await session.execute(
        select(EstablishmentAmenity.establishment_id)
        .where(
            EstablishmentAmenity.amenity_id == amenity.id,
        )
        .limit(1)
    )

    if link_result.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Retirez d'abord cet équipement des établissements "
                "qui l'utilisent."
            ),
        )

    _audit(
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
            detail="Impossible de supprimer cet équipement.",
        ) from exc

    return {"message": "Équipement supprimé."}

@admin_establishment_amenities_router.post("/{establishment_id}/amenities")
async def add_establishment_amenities(
    establishment_id: UUID,
    data: EstablishmentAmenityRequest,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    establishment = await _get_establishment(
        establishment_id,
        session,
        for_update=True,
    )
    amenity_result = await session.execute(
        select(Amenity.id).where(
            Amenity.id.in_(data.amenity_ids),
            Amenity.id.isnot(None),
        )
    )
    active_ids = set(amenity_result.scalars().all())
    missing_ids = set(data.amenity_ids) - active_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Un ou plusieurs équipements n'existent pas ou sont supprimés.",
        )

    existing_result = await session.execute(
        select(EstablishmentAmenity.amenity_id).where(
            EstablishmentAmenity.establishment_id == establishment.id,
            EstablishmentAmenity.amenity_id.in_(data.amenity_ids),
        )
    )
    existing_ids = set(existing_result.scalars().all())
    new_ids = active_ids - existing_ids
    for amenity_id in new_ids:
        session.add(
            EstablishmentAmenity(
                establishment_id=establishment.id,
                amenity_id=amenity_id,
            )
        )
    _audit(
        session,
        actor,
        "ADMIN_ESTABLISHMENT_AMENITIES_UPDATED",
        request,
        establishment_id=establishment.id,
        metadata={
            "added_ids": [str(item) for item in sorted(new_ids)],
            "requested_count": len(data.amenity_ids),
        },
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Les équipements ont changé pendant cette requête; recommencez.",
        ) from exc
    return {
        "added_count": len(new_ids),
        "already_attached_count": len(existing_ids),
    }


@admin_establishment_amenities_router.delete(
    "/{establishment_id}/amenities/{amenity_id}"
)
async def remove_establishment_amenity(
    establishment_id: UUID,
    amenity_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    establishment = await _get_establishment(
        establishment_id,
        session,
        for_update=True,
    )
    result = await session.execute(
        select(EstablishmentAmenity).where(
            EstablishmentAmenity.establishment_id == establishment.id,
            EstablishmentAmenity.amenity_id == amenity_id,
        )
    )
    link = result.scalars().first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cet équipement n'est pas associé à l'établissement.",
        )
    await session.delete(link)
    _audit(
        session,
        actor,
        "ADMIN_ESTABLISHMENT_AMENITY_REMOVED",
        request,
        establishment_id=establishment.id,
        metadata={"amenity_id": str(amenity_id)},
    )
    await session.commit()
    return {"message": "Équipement retiré de l'établissement."}