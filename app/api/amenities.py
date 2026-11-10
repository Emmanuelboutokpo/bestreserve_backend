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
    EstablishmentAmenity,
    User,
)
from app.models.base import utc_now
from app.schemas.amenity import (
    AmenityCreate,
    AmenityPage,
    AmenityPatch,
    AmenityPublic,
)


amenities_router = APIRouter(prefix="/amenities", tags=["Équipements"])

admin_amenities_router = APIRouter(
    prefix="/admin/amenities",
    tags=["Administration des équipements"],
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
