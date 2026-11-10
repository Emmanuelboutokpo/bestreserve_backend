from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.schemas.establishment import (
    EstablishmentAdminDetailPublic,
    EstablishmentPage,
)
from app.services.establishment import establishment_service


admin_establishments_router = APIRouter(
    prefix="/admin/establishments",
    tags=["Administration - Suivi des établissements"],
    dependencies=[Depends(require_admin)],
)


@admin_establishments_router.get(
    "",
    response_model=EstablishmentPage,
    summary="Lister les établissements de la plateforme",
)
async def list_establishments_admin(
    q: str | None = Query(default=None, min_length=2, max_length=200),
    category_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    sort: Literal[
        "newest", "rating", "price_asc", "price_desc", "name"
    ] = "newest",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    return await establishment_service.list_admin_establishments(
        db,
        q=q,
        category_id=category_id,
        status_filter=status_filter,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@admin_establishments_router.get(
    "/{establishment_id}",
    response_model=EstablishmentAdminDetailPublic,
    summary="Consulter un établissement de la plateforme",
)
async def get_establishment_admin(
    establishment_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    establishment = await establishment_service._get_admin_establishment(
        establishment_id,
        db,
    )
    data = establishment_service.serialize_detail(establishment)
    data["status"] = establishment.status
    return data
