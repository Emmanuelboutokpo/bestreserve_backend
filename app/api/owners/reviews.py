# app/api/admin/reviews.py

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import User

from app.schemas.reviews import (
    ReviewAdminPublic,
    ReviewPage,
    ReviewReportPublic,
)

from app.services import reviews as review_service


owner_reviews_router = APIRouter(
    prefix="/owners/reviews",
    tags=["Propriétaire - Avis"],
    dependencies=[Depends(require_proprietaire)],
)


@owner_reviews_router.get(
    "",
    response_model=ReviewPage,
    summary="Lister et filtrer les avis",
)
async def list_admin_reviews(
    actor: User = Depends(require_proprietaire),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    approved: bool | None = None,
    establishment_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await review_service.list_admin_reviews(
        limit=limit,
        offset=offset,
        approved=approved,
        establishment_id=establishment_id,
        session=session,
        owner_id=actor.id,
    )

@owner_reviews_router.patch(
    "/{review_id}/approve",
    response_model=ReviewAdminPublic,
    summary="Approuver un avis",
)
async def approve_review(
    review_id: UUID,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await review_service.approve_review(
        review_id=review_id,
        session=session,
        owner_id=actor.id,
    )


@owner_reviews_router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un avis depuis le propriétaire",
)
async def delete_owner_review(
    review_id: UUID,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    await review_service.delete_admin_review(
        review_id=review_id,
        session=session,
        owner_id=actor.id,
    )