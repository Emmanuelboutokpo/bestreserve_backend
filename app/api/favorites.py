from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_client
from app.models import User
from app.schemas.favorite import FavoritePage
from app.services.favorite import FavoriteService


favorites_router = APIRouter(
    prefix="/users/me/favorites",
    tags=["Favoris client"],
    dependencies=[Depends(require_client)],
)


# ---------------------------------------------------------
# GET : LISTER MES FAVORIS
# ---------------------------------------------------------

@favorites_router.get("", response_model=FavoritePage)
async def list_my_favorites(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    return await FavoriteService.list_my_favorites(
        user_id=current_user.id,
        session=session,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------
# POST : AJOUTER UN FAVORI
# ---------------------------------------------------------

@favorites_router.post(
    "/{establishment_id}",
    status_code=status.HTTP_201_CREATED,
)
async def add_favorite(
    establishment_id: UUID,
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    return await FavoriteService.add_favorite(
        user_id=current_user.id,
        establishment_id=establishment_id,
        session=session,
    )


# ---------------------------------------------------------
# DELETE : RETIRER UN FAVORI
# ---------------------------------------------------------

@favorites_router.delete("/{establishment_id}")
async def remove_favorite(
    establishment_id: UUID,
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    return await FavoriteService.remove_favorite(
        user_id=current_user.id,
        establishment_id=establishment_id,
        session=session,
    )


# ---------------------------------------------------------
# DELETE : VIDER MES FAVORIS
# ---------------------------------------------------------

@favorites_router.delete("")
async def clear_my_favorites(
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    return await FavoriteService.clear_my_favorites(
        user_id=current_user.id,
        session=session,
    )
