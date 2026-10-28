from decimal import Decimal
from typing import Literal, Optional, Any
from uuid import UUID
from datetime import date, time
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.schemas.establishment import (
    EstablishmentDetailPublic,
    EstablishmentListItem,
    EstablishmentPage,
    ReviewPage
)
from app.services.establishment import establishment_service


establishments_router = APIRouter(
    prefix="/establishments",
    tags=["Établissements"],
)

@establishments_router.get(
    "",
    response_model=EstablishmentPage,
    summary="Liste publique des établissements",
)
async def list_establishments(
    # Recherche textuelle
    q: Optional[str] = Query(
        None,
        min_length=2,
        max_length=200,
        description="Recherche par nom ou description",
    ),

    # Filtres principaux
    category_id: Optional[UUID] = None,
    subcategory_id: Optional[UUID] = None,
    location_id: Optional[UUID] = None,

    # Équipements : plusieurs identifiants possibles
    amenity_ids: Optional[list[UUID]] = Query(
        None,
        description="Identifiants des équipements recherchés",
    ),

    # Prix et note
    minimum_price: Optional[Decimal] = Query(None, ge=0),
    maximum_price: Optional[Decimal] = Query(None, ge=0),
    minimum_rating: Optional[Decimal] = Query(None, ge=0, le=5),

    # Hébergement
    check_in: Optional[date] = Query(
        None,
        description="Date d'arrivée",
    ),
    check_out: Optional[date] = Query(
        None,
        description="Date de départ",
    ),

    # Restaurant
    reservation_date: Optional[date] = Query(
        None,
        description="Date de réservation au restaurant",
    ),
    arrival_time: Optional[time] = Query(
        None,
        description="Heure d'arrivée souhaitée",
    ),

    # Nombre de voyageurs ou de personnes
    guests: Optional[int] = Query(
        None,
        ge=1,
        description="Nombre de voyageurs ou de personnes",
    ),

    # Loisirs
    activity_type_id: Optional[UUID] = Query(
        None,
        description="Identifiant de la sous-catégorie d'activité",
    ),
    activity_date: Optional[date] = Query(
        None,
        description="Date de l'activité",
    ),
    participants: Optional[int] = Query(
        None,
        ge=1,
        description="Nombre de participants",
    ),

    # Tri
    sort: Literal[
        "newest",
        "rating",
        "price_asc",
        "price_desc",
        "name",
    ] = "newest",

    # Pagination
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),

    # Base de données
    db: AsyncSession = Depends(get_session),
):
    return await establishment_service.list_establishments(
        db,

        # Recherche textuelle
        q=q,

        # Filtres principaux
        category_id=category_id,
        subcategory_id=subcategory_id,
        location_id=location_id,
        amenity_ids=amenity_ids,

        # Prix et note
        minimum_price=minimum_price,
        maximum_price=maximum_price,
        minimum_rating=minimum_rating,

        # Hébergement
        check_in=check_in,
        check_out=check_out,

        # Restaurant
        reservation_date=reservation_date,
        arrival_time=arrival_time,

        # Nombre de personnes
        guests=guests,

        # Loisirs
        activity_type_id=activity_type_id,
        activity_date=activity_date,
        participants=participants,

        # Tri et pagination
        sort=sort,
        limit=limit,
        offset=offset,
    )


# ---------- ÉTABLISSEMENTS POPULAIRES ----------

@establishments_router.get(
    "/popular",
    response_model=EstablishmentPage,
    summary="Liste des établissements populaires",
)
async def list_popular_establishments(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    """
    Retourne les établissements publiés les plus populaires.
    """

    return await establishment_service.list_popular_establishments(
        db,
        limit=limit,
        offset=offset,
    )

# ---------- ÉTABLISSEMENTS PROCHES ----------

@establishments_router.get(
    "/nearby",
    response_model=EstablishmentPage,
    summary="Établissements proches d'une position",
)
async def list_nearby_establishments(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, gt=0, le=200),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    """
    Recherche les établissements publiés à proximité
    d'une position géographique.
    """

    return await establishment_service.list_nearby_establishments(
        db,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
    )

@establishments_router.get(
    "/{slug}",
    response_model=EstablishmentDetailPublic,
    summary="Détail public par slug",
)
async def get_establishment(
    slug: str,
    db: AsyncSession = Depends(get_session),
):
    establishment = (
        await establishment_service.get_establishment_by_slug(db, slug)
    )
    return establishment_service.serialize_detail(establishment)


@establishments_router.get(
    "/{establishment_id}/reviews",
    response_model=ReviewPage,
    summary="Avis paginés d'un établissement",
)
async def list_establishment_reviews(
    establishment_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    return await establishment_service.list_reviews(
        db,
        establishment_id,
        limit=limit,
        offset=offset,
    )


@establishments_router.get(
    "/{establishment_id}/similar",
    response_model=list[EstablishmentListItem],
    summary="Établissements similaires",
)
async def list_similar_establishments(
    establishment_id: UUID,
    limit: int = Query(default=8, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
):
    return await establishment_service.list_similar(
        db=db,
        establishment_id=establishment_id,
        limit=limit,
    )