from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
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


def _category_create_data(name: str, icon: str | None) -> CategoryCreate:
    try:
        return CategoryCreate(name=name, icon=icon)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


def _category_patch_data(
    name: str | None,
    icon: str | None,
) -> CategoryPatch:
    changes = {}
    if name is not None:
        changes["name"] = name
    if icon is not None:
        changes["icon"] = icon or None
    try:
        return CategoryPatch.model_validate(changes)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@admin_categories_router.post(
    "",
    response_model=CategoryPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    request: Request,
    name: Annotated[str, Form(min_length=2, max_length=100)],
    icon: Annotated[str | None, Form(max_length=100)] = None,
    img: UploadFile | None = File(
        default=None,
        description="Image de la catégorie (JPEG, PNG ou WebP, 5 Mo maximum).",
    ),
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    data = _category_create_data(name, icon)
    return await category_service.create(
        data,
        actor,
        request,
        session,
        image=img,
    )


@admin_categories_router.patch(
    "/{category_id}",
    response_model=CategoryPublic,
)
async def update_category(
    category_id: UUID,
    request: Request,
    name: Annotated[str | None, Form(min_length=2, max_length=100)] = None,
    icon: Annotated[str | None, Form(max_length=100)] = None,
    img: UploadFile | None = File(
        default=None,
        description="Nouvelle image de la catégorie (JPEG, PNG ou WebP, 5 Mo maximum).",
    ),
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    data = _category_patch_data(name, icon)
    return await category_service.update(
        category_id,
        data,
        actor,
        request,
        session,
        image=img,
    )


@admin_categories_router.delete(
    "/{category_id}/image",
    response_model=CategoryPublic,
)
async def delete_category_image(
    category_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await category_service.delete_image(
        category_id,
        actor,
        request,
        session,
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