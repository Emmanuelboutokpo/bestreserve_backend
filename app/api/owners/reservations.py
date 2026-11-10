"""Routes d'administration pour les réservations BestRev."""

from datetime import date
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire

from app.models import User
from app.schemas.reservation import (
    AdminRefundRequest,
    AdminReservationPage,
    AdminReservationPublic,
    AdminReservationStats,
    AdminReservationStatusRequest,
)
from app.services import reservation as reservation_service

owner_reservations_router = APIRouter(
    prefix="/owners/reservations",
    tags=["Propriétaire - Réservations"],
    dependencies=[Depends(require_proprietaire)],
)


@owner_reservations_router.get(
    "",
    response_model=AdminReservationPage,
    summary="Lister et filtrer les réservations",
)
async def list_reservations(
    owner: Annotated[User, Depends(require_proprietaire)],
    session: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    establishment_id: UUID | None = None,
    user_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = Query(default=None, max_length=200),
):
    return await reservation_service.list_admin_reservations(
        session=session,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        establishment_id=establishment_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        owner_id=owner.id,
    )


@owner_reservations_router.get(
    "/stats",
    response_model=AdminReservationStats,
    summary="Consulter les statistiques de réservation",
)
async def reservation_stats(
    owner: Annotated[User, Depends(require_proprietaire)],
    session: AsyncSession = Depends(get_session),
    start_date: date | None = None,
    end_date: date | None = None,
):
    return await reservation_service.get_reservation_stats(
        session=session,
        start_date=start_date,
        end_date=end_date,
        owner_id=owner.id,
    )


@owner_reservations_router.get(
    "/{reservation_id}",
    response_model=AdminReservationPublic,
    summary="Consulter le détail d'une réservation",
)
async def get_reservation(
    reservation_id: UUID,
    owner: Annotated[User, Depends(require_proprietaire)],
    session: AsyncSession = Depends(get_session),
):
    return await reservation_service.get_admin_reservation(
        reservation_id=reservation_id,
        session=session,
        owner_id=owner.id,
    )


@owner_reservations_router.patch(
    "/{reservation_id}/status",
    response_model=AdminReservationPublic,
    summary="Modifier le statut d'une réservation",
)
async def change_reservation_status(
    reservation_id: UUID,
    data: AdminReservationStatusRequest,
    request: Request,
    admin_user: Annotated[User, Depends(require_proprietaire)],
    session: AsyncSession = Depends(get_session),
):
    return await reservation_service.update_reservation_status(
        reservation_id=reservation_id,
        data=data,
        admin_user=admin_user,
        session=session,
        request=request,
        reason=data.reason,
        owner_id=admin_user.id,
    )


@owner_reservations_router.post(
    "/{reservation_id}/refund",
    response_model=AdminReservationPublic,
    summary="Enregistrer un remboursement déjà effectué",
)
async def refund_reservation(
    reservation_id: UUID,
    data: AdminRefundRequest,
    request: Request,
    admin_user: Annotated[User, Depends(require_proprietaire)],
    session: AsyncSession = Depends(get_session),
):
    return await reservation_service.record_reservation_refund(
        reservation_id=reservation_id,
        data=data,
        admin_user=admin_user,
        session=session,
        request=request,
        owner_id=admin_user.id,
    )
