from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import User
from app.services import stats as stats_service


stats_router = APIRouter(
    prefix="/owners/stats",
    tags=["Statistiques propriétaire"],
    dependencies=[Depends(require_proprietaire)],
)


@stats_router.get("/overview")
async def stats_overview(
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_stats_overview(
        session,
        owner_id=actor.id,
    )


@stats_router.get("/users")
async def stats_users(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_stats_users(
        session,
        start_date,
        end_date,
        owner_id=actor.id,
    )


@stats_router.get("/establishments")
async def stats_establishments(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_stats_establishments(
        session,
        start_date,
        end_date,
        owner_id=actor.id,
    )


@stats_router.get("/reservations")
async def stats_reservations(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_stats_reservations(
        session,
        start_date,
        end_date,
        owner_id=actor.id,
    )


@stats_router.get("/revenue")
async def stats_revenue(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_stats_revenue(
        session,
        start_date,
        end_date,
        owner_id=actor.id,
    )


@stats_router.get("/top-destinations")
async def top_destinations(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_top_destinations(
        session,
        start_date,
        end_date,
        limit,
        owner_id=actor.id,
    )


@stats_router.get("/top-establishments")
async def top_establishments(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_top_establishments(
        session,
        start_date,
        end_date,
        limit,
        owner_id=actor.id,
    )


@stats_router.get("/recent-activities")
async def recent_activities(
    actor: User = Depends(require_proprietaire),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_recent_activities(
        session,
        limit,
        offset,
        owner_id=actor.id,
    )


@stats_router.get("/charts/reservations")
async def reservations_chart(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    period: Literal["day", "week", "month"] = "day",
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_reservations_chart(
        session,
        start_date,
        end_date,
        period,
        owner_id=actor.id,
    )


@stats_router.get("/charts/categories")
async def categories_chart(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_categories_chart(
        session,
        start_date,
        end_date,
        owner_id=actor.id,
    )


@stats_router.get("/charts/revenue")
async def revenue_chart(
    actor: User = Depends(require_proprietaire),
    start_date: date | None = None,
    end_date: date | None = None,
    period: Literal["day", "week", "month"] = "day",
    currency: str = Query(default="XOF", min_length=3, max_length=3),
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_revenue_chart(
        session,
        start_date,
        end_date,
        period,
        currency,
        owner_id=actor.id,
    )
