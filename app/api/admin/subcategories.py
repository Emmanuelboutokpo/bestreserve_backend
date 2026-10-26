from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User
from app.schemas.subcategory import SubcategoryPatch, SubcategoryPublic
from app.services.subcategory import SubcategoryService

admin_subcategories_router = APIRouter(
    prefix="/admin/subcategories",
    tags=["Administration des sous-catégories"],
    dependencies=[Depends(require_admin)],
)

subcategory_service = SubcategoryService()

@admin_subcategories_router.patch(
    "/{subcategory_id}",
    response_model=SubcategoryPublic,
)
async def update_subcategory(
    subcategory_id: UUID,
    data: SubcategoryPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.update(
        subcategory_id, data, actor, request, session
    )


@admin_subcategories_router.delete("/{subcategory_id}")
async def delete_subcategory(
    subcategory_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await subcategory_service.delete(
        subcategory_id, actor, request, session
    )