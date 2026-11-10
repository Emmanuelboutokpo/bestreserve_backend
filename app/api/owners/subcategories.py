from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import User
from app.schemas.subcategory import SubcategoryCreate, SubcategoryPublic
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