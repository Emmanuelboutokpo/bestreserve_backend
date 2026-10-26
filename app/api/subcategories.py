from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User
from app.schemas.subcategory import (
    SubcategoryPage,
    SubcategoryPatch,
    SubcategoryPublic,
)

from app.services.subcategory import SubcategoryService

subcategory_service = SubcategoryService()

subcategories_router = APIRouter(
    prefix="/subcategories",
    tags=["Sous-catégories"],
)

admin_subcategories_router = APIRouter(
    prefix="/admin/subcategories",
    tags=["Administration des sous-catégories"],
    dependencies=[Depends(require_admin)],
)


# ── Public ────────────────────────────────────────────────────────────────

@subcategories_router.get("", response_model=SubcategoryPage)
async def list_subcategories(
    category_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.list(
        session,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )


@subcategories_router.get("/{subcategory_id}", response_model=SubcategoryPublic)
async def get_subcategory(
    subcategory_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.get_by_id(subcategory_id, session)
