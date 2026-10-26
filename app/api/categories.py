from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.schemas.category import CategoryPublic, CategoryPage
from app.schemas.subcategory import  SubcategoryPage

from app.services.category import CategoryService
from app.services.subcategory import SubcategoryService


categories_router = APIRouter(prefix="/categories", tags=["Catégories"])

admin_categories_router = APIRouter(
    prefix="/admin/categories",
    tags=["Administration des catégories"],
    dependencies=[Depends(require_admin)],
)

category_service = CategoryService()
subcategory_service = SubcategoryService()

# ── Public ────────────────────────────────────────────────────────────────

@categories_router.get("", response_model=CategoryPage)
async def list_categories(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await category_service.list(session, limit=limit, offset=offset)


@categories_router.get("/{category_id}", response_model=CategoryPublic)
async def get_category(
    category_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await category_service.get_by_id(category_id, session)


@categories_router.get(
    "/{category_id}/subcategories",
    response_model=SubcategoryPage,
)
async def list_category_subcategories(
    category_id: UUID,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.list_by_category(
        category_id, session, limit=limit, offset=offset
    )
 