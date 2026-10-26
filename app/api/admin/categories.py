from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User
from app.schemas.category import CategoryCreate, CategoryPatch, CategoryPublic
from app.schemas.subcategory import SubcategoryCreate, SubcategoryPublic
from app.services.category import CategoryService
from app.services.subcategory import SubcategoryService


admin_categories_router = APIRouter(
    prefix="/admin/categories",
    tags=["Administration des catégories"],
    dependencies=[Depends(require_admin)],
)

category_service = CategoryService()
subcategory_service = SubcategoryService()

@admin_categories_router.post(
    "",
    response_model=CategoryPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: CategoryCreate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await category_service.create(data, actor, request, session)


@admin_categories_router.patch(
    "/{category_id}",
    response_model=CategoryPublic,
)
async def update_category(
    category_id: UUID,
    data: CategoryPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await category_service.update(
        category_id, data, actor, request, session
    )


@admin_categories_router.delete("/{category_id}")
async def delete_category(
    category_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await category_service.delete(
        category_id, actor, request, session
    )


@admin_categories_router.post(
    "/{category_id}/subcategories",
    response_model=SubcategoryPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_subcategory(
    category_id: UUID,
    data: SubcategoryCreate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.create(
        category_id, data, actor, request, session
    )