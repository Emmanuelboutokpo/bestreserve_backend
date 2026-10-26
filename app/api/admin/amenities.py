from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User
from app.schemas.amenity import (
    AmenityCreate,
    AmenityPatch,
    AmenityPublic,
    EstablishmentAmenityRequest,
)
from app.services.amenity import AmenityService


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
    return await AmenityService.create_amenity(
        data,
        request,
        actor,
        session,
    )


@admin_amenities_router.patch(
    "/{amenity_id}",
    response_model=AmenityPublic,
)
async def update_amenity(
    amenity_id: UUID,
    data: AmenityPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await AmenityService.update_amenity(
        amenity_id,
        data,
        request,
        actor,
        session,
    )


@admin_amenities_router.delete("/{amenity_id}")
async def delete_amenity(
    amenity_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await AmenityService.delete_amenity(
        amenity_id,
        request,
        actor,
        session,
    )


@admin_establishment_amenities_router.post(
    "/{establishment_id}/amenities"
)
async def add_establishment_amenities(
    establishment_id: UUID,
    data: EstablishmentAmenityRequest,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await AmenityService.add_establishment_amenities(
        establishment_id,
        data,
        request,
        actor,
        session,
    )


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
    return await AmenityService.remove_establishment_amenity(
        establishment_id,
        amenity_id,
        request,
        actor,
        session,
    )
