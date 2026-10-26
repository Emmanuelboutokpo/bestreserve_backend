"""Routes client pour les réservations BestRev."""

from datetime import date, time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_client
from app.models import User
from app.schemas.reservation import (
    PublicAvailability,
    ReservationCreate,
    ReservationPage,
    ReservationPublic,
    ReservationQuote,
    ReservationUpdate,
    ReservationCancelRequest,
)
from app.services import reservation as reservation_service

reservations_router = APIRouter(tags=["Réservations"])


@reservations_router.get(
    "/reservations/check-availability",
    response_model=PublicAvailability,
    summary="Vérifier la disponibilité d'un établissement",
)
async def check_availability(
    establishment_id: UUID,
    start_date: date,
    session: AsyncSession = Depends(get_session),
    end_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    quantity: int = Query(default=1, ge=1, le=100),
    adults: int = Query(default=1, ge=1, le=1000),
    children: int = Query(default=0, ge=0, le=1000),
):
    return await reservation_service.check_establishment_availability(
        establishment_id=establishment_id,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        quantity=quantity,
        adults=adults,
        children=children,
        session=session,
    )


@reservations_router.post(
    "/reservations/quote",
    response_model=ReservationQuote,
    summary="Calculer un devis sans créer de réservation",
)
async def quote_reservation(
    data: ReservationCreate,
    session: AsyncSession = Depends(get_session),
):
    _, quote = await reservation_service.reservation_quote(data, session)
    return quote


@reservations_router.get(
    "/users/me/reservations",
    response_model=ReservationPage,
    summary="Lister les réservations du client connecté",
)
async def list_my_reservations(
    current_user: Annotated[User, Depends(require_client)],
    session: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
):
    return await reservation_service.list_client_reservations(
        user_id=current_user.id,
        session=session,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )


@reservations_router.get(
    "/users/me/reservations/{reference}",
    response_model=ReservationPublic,
    summary="Consulter une réservation du client par sa référence",
)
async def get_my_reservation(
    reference: str,
    current_user: Annotated[User, Depends(require_client)],
    session: AsyncSession = Depends(get_session),
):
    return await reservation_service.get_client_reservation_by_reference(
        reference=reference,
        user_id=current_user.id,
        session=session,
    )


@reservations_router.post(
    "/reservations",
    response_model=ReservationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une demande de réservation",
)
async def create_reservation(
    data: ReservationCreate,
    request: Request,
    current_user: Annotated[User, Depends(require_client)],
    session: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        max_length=255,
    ),
):
    return await reservation_service.create_client_reservation(
        data=data,
        current_user=current_user,
        session=session,
        request=request,
        idempotency_key=idempotency_key,
    )


@reservations_router.post(
    "/users/me/reservations/{reservation_id}/cancel",
    response_model=ReservationPublic,
    summary="Demander l'annulation d'une réservation",
)
async def cancel_reservation(
    reservation_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_client)],
    session: AsyncSession = Depends(get_session),
    data: ReservationCancelRequest | None = None,
):
    return await reservation_service.cancel_client_reservation(
        reservation_id=reservation_id,
        user_id=current_user.id,
        session=session,
        request=request,
        reason=data.reason if data else None,
    )
