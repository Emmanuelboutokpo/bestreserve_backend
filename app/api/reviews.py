# app/api/reviews.py

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_client
from app.models import User
from app.schemas.establishment import ReviewPublic
from app.schemas.reviews import ReviewCreate, ReviewUpdate
from app.services import reviews as review_service


reviews_router = APIRouter(tags=["Avis"])


@reviews_router.get(
    "/establishments/{establishment_id}/reviews",
    response_model=list[ReviewPublic],
    summary="Lister les avis publics d'un établissement",
)
async def list_establishment_reviews(
    establishment_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await review_service.list_establishment_reviews(
        establishment_id=establishment_id,
        limit=limit,
        offset=offset,
        session=session,
    )


@reviews_router.post(
    "/establishments/{establishment_id}/reviews",
    response_model=ReviewPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un avis",
)
async def create_review(
    establishment_id: UUID,
    data: ReviewCreate,
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    return await review_service.create_review(
        establishment_id=establishment_id,
        data=data,
        current_user=current_user,
        session=session,
    )


@reviews_router.put(
    "/reviews/{review_id}",
    response_model=ReviewPublic,
    summary="Modifier son avis",
)
async def update_review(
    review_id: UUID,
    data: ReviewUpdate,
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    return await review_service.update_review(
        review_id=review_id,
        data=data,
        current_user=current_user,
        session=session,
    )


@reviews_router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer son avis",
)
async def delete_review(
    review_id: UUID,
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    await review_service.delete_review(
        review_id=review_id,
        current_user=current_user,
        session=session,
    )

