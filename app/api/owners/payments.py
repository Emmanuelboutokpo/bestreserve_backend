# app/api/admin_payments.py

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import User
from app.services.payment import (
    get_admin_payment,
    get_admin_payment_stats,
    list_admin_payments,
)

owner_payments_router = APIRouter(
    prefix="/owners/payments",
    tags=["Propriétaire - Paiements"],
    dependencies=[Depends(require_proprietaire)],
)


# ============================================================
# OWNER : LISTER ET FILTRER LES TRANSACTIONS
# ============================================================

@owner_payments_router.get(
    "",
    summary="Lister et filtrer les transactions",
)
async def list_payments(
    owner: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    transaction_type: str | None = Query(
        default=None,
        alias="type",
    ),
    provider: str | None = Query(
        default=None,
        max_length=50,
    ),
    user_id: UUID | None = None,
    reservation_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = Query(
        default=None,
        max_length=200,
    ),
):
 
    return await list_admin_payments(
        session=session,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        transaction_type=transaction_type,
        provider=provider,
        user_id=user_id,
        reservation_id=reservation_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        owner_id=owner.id,
    )


# ============================================================
# ADMIN : STATISTIQUES
# ============================================================

@owner_payments_router.get(
    "/stats",
    summary="Consulter les statistiques des paiements",
)
async def payment_stats(
    owner: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = Query(
        default=None,
        max_length=50,
    ),
):
 
    return await get_admin_payment_stats(
        session=session,
        start_date=start_date,
        end_date=end_date,
        provider=provider,
        owner_id=owner.id,
    )


# ============================================================
# ADMIN : DÉTAIL D'UNE TRANSACTION
# ============================================================

@owner_payments_router.get(
    "/{transaction_id}",
    summary="Consulter le détail d'une transaction",
)
async def payment_detail(
    transaction_id: UUID,
    owner: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
 
    return await get_admin_payment(
        transaction_id=transaction_id,
        session=session,
        owner_id=owner.id,
    )