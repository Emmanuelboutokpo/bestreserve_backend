from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import User
from app.schemas.subcategory import SubcategoryCreate, SubcategoryPublic, SubcategoryPatch
from app.services.subcategory import SubcategoryService

owner_subcategories_router = APIRouter(
    prefix="/owners/categories",
    tags=["Partenaires - Sous-catégories"],
    dependencies=[Depends(require_proprietaire)],
)

subcategory_service = SubcategoryService()


@owner_subcategories_router.post(
    "/{category_id}/subcategories",
    response_model=SubcategoryPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_subcategory(
    category_id: UUID,
    data: SubcategoryCreate,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.create(
        category_id,
        data,
        actor,
        request,
        session,
        audit_action="OWNER_SUBCATEGORY_CREATED",
    )


@owner_subcategories_router.patch(
    "/{subcategory_id}",
    response_model=SubcategoryPublic,
)
async def update_subcategory(
    subcategory_id: UUID,
    data: SubcategoryPatch,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.update(
        subcategory_id, data, actor, request, session
    )


@owner_subcategories_router.delete("/{subcategory_id}")
async def delete_subcategory(
    subcategory_id: UUID,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.delete(
        subcategory_id, actor, request, session
    )