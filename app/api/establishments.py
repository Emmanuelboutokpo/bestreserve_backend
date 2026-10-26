from decimal import Decimal
from typing import Literal, Optional, Any
from uuid import UUID

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
    q: Optional[str] = Query(None, min_length=2, max_length=200),
    category_id: Optional[UUID] = None,
    subcategory_id: Optional[UUID] = None,
    location_id: Optional[UUID] = None,
    minimum_price: Optional[Decimal] = Query(None, ge=0),
    maximum_price: Optional[Decimal] = Query(None, ge=0),
    minimum_rating: Optional[Decimal] = Query(None, ge=0, le=5),
    sort: Literal[
        "newest", "rating", "price_asc", "price_desc", "name"
    ] = "newest",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    return await establishment_service.list_establishments(
        db,
        q=q,
        category_id=category_id,
        subcategory_id=subcategory_id,
        location_id=location_id,
        minimum_price=minimum_price,
        maximum_price=maximum_price,
        minimum_rating=minimum_rating,
        sort=sort,
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