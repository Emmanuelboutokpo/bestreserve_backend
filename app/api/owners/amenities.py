from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import User
from app.schemas.amenity import EstablishmentAmenityRequest
from app.services.amenity import AmenityService


owner_establishment_amenities_router = APIRouter(
    prefix="/owners/establishments",
    tags=["Partenaires - Équipements des établissements"],
    dependencies=[Depends(require_proprietaire)],
)


@owner_establishment_amenities_router.post(
    "/{establishment_id}/amenities"
)
async def add_establishment_amenities(
    establishment_id: UUID,
    data: EstablishmentAmenityRequest,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await AmenityService.add_establishment_amenities(
        establishment_id,
        data,
        request,
        actor,
        session,
        owner_id=actor.id,
    )


@owner_establishment_amenities_router.delete(
    "/{establishment_id}/amenities/{amenity_id}"
)
async def remove_establishment_amenity(
    establishment_id: UUID,
    amenity_id: UUID,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await AmenityService.remove_establishment_amenity(
        establishment_id,
        amenity_id,
        request,
        actor,
        session,
        owner_id=actor.id,
    )
