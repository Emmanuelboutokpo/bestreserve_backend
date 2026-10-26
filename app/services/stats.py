from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import StringIO
from typing import Literal, Any

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import (
    ActivityLog,
    Category,
    Establishment,
    Location,
    Reservation,
    Transaction,
    User,
)
from app.models.enums import (
    EstablishmentStatus,
    PaymentStatus,
    ReservationStatus,
    TransactionType,
    UserRole,
    UserStatus,
)

ZERO = Decimal("0.00")
MAX_PERIOD_DAYS = 366 * 5
ChartPeriod = Literal["day", "week", "month"]


def _date_bounds(
    start_date: date | None,
    end_date: date | None,
) -> tuple[datetime | None, datetime | None]:
    """Convert inclusive date filters into UTC datetime bounds."""
    today = date.today()
    earliest = today - timedelta(days=MAX_PERIOD_DAYS)
    latest = today + timedelta(days=MAX_PERIOD_DAYS)

    if start_date is not None and end_date is None:
        end_date = start_date + timedelta(days=MAX_PERIOD_DAYS)
    elif end_date is not None and start_date is None:
        start_date = end_date - timedelta(days=MAX_PERIOD_DAYS)

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La date de début dépasse la date de fin.",
        )

    if start_date and end_date and (end_date - start_date).days > MAX_PERIOD_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La période ne peut pas dépasser cinq ans.",
        )

    if (
        (start_date and not earliest <= start_date <= latest)
        or (end_date and not earliest <= end_date <= latest)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Les bornes doivent rester dans les cinq dernières/prochaines années.",
        )

    start = (
        datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        if start_date is not None
        else None
    )
    # End date is inclusive for the caller; SQL uses an exclusive upper bound.
    end = (
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        if end_date is not None
        else None
    )
    return start, end


def _in_period(column: Any, start: datetime | None, end: datetime | None) -> list:
    filters = []
    if start is not None:
        filters.append(column >= start)
    if end is not None:
        filters.append(column < end)
    return filters


def _safe_csv_cell(value: Any) -> str:
    """Mitigate CSV formula injection in spreadsheet applications."""
    text = "" if value is None else str(value)
    if text.lstrip(" \\t\\r\\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


async def _count(session: AsyncSession, model: Any, *filters: Any) -> int:
    statement = select(func.count(model.id))
    if filters:
        statement = statement.where(*filters)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def get_stats_overview(session: AsyncSession) -> dict:
    users_result = await session.execute(
        select(
            func.count(User.id),
            func.sum(case((User.role == UserRole.CLIENT, 1), else_=0)),
            func.sum(case((User.role == UserRole.ADMIN, 1), else_=0)),
        )
    )
    total_users, clients, admins = users_result.one()

    users_active = await _count(
        session, User, User.status == UserStatus.ACTIF
    )
    establishments_total = await _count(session, Establishment)
    establishments_published = await _count(
        session,
        Establishment,
        Establishment.status == EstablishmentStatus.PUBLIE,
    )
    reservation_total = await _count(session, Reservation)
    pending_reservations = await _count(
        session,
        Reservation,
        Reservation.status == ReservationStatus.EN_ATTENTE,
    )

    payments_result = await session.execute(
        select(
            Transaction.currency,
            func.coalesce(
                func.sum(
                    case(
                        (
                            Transaction.type == TransactionType.PAYMENT,
                            Transaction.amount,
                        ),
                        else_=ZERO,
                    )
                ),
                ZERO,
            ),
            func.count(Transaction.id),
        )
        .where(
            Transaction.type == TransactionType.PAYMENT,
            Transaction.status == PaymentStatus.PAYE,
        )
        .group_by(Transaction.currency)
        .order_by(Transaction.currency)
    )

    return {
        "users": {
            "total": int(total_users or 0),
            "active": users_active,
            "clients": int(clients or 0),
            "admins": int(admins or 0),
        },
        "establishments": {
            "total": establishments_total,
            "published": establishments_published,
        },
        "reservations": {
            "total": reservation_total,
            "pending": pending_reservations,
        },
        "payments": {
            "by_currency": [
                {
                    "currency": currency,
                    "gross_paid": amount,
                    "paid_count": count,
                }
                for currency, amount, count in payments_result.all()
            ]
        },
    }


async def get_stats_users(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start, end = _date_bounds(start_date, end_date)
    result = await session.execute(
        select(
            func.count(User.id),
            func.sum(case((User.status == UserStatus.ACTIF, 1), else_=0)),
            func.sum(case((User.status == UserStatus.INACTIF, 1), else_=0)),
            func.sum(case((User.status == UserStatus.EN_ATTENTE, 1), else_=0)),
            func.sum(case((User.status == UserStatus.SUSPENDU, 1), else_=0)),
            func.sum(case((User.role == UserRole.CLIENT, 1), else_=0)),
            func.sum(case((User.role == UserRole.ADMIN, 1), else_=0)),
        ).where(*_in_period(User.created_at, start, end))
    )
    total, active, inactive, pending, suspended, clients, admins = result.one()
    return {
        "total": int(total or 0),
        "active": int(active or 0),
        "inactive": int(inactive or 0),
        "pending": int(pending or 0),
        "suspended": int(suspended or 0),
        "clients": int(clients or 0),
        "admins": int(admins or 0),
        "start_date": start_date,
        "end_date": end_date,
    }


async def get_stats_establishments(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start, end = _date_bounds(start_date, end_date)
    result = await session.execute(
        select(
            func.count(Establishment.id),
            func.sum(case((Establishment.status == EstablishmentStatus.PUBLIE, 1), else_=0)),
            func.sum(case((Establishment.status == EstablishmentStatus.EN_ATTENTE, 1), else_=0)),
            func.sum(case((Establishment.status == EstablishmentStatus.REJETE, 1), else_=0)),
            func.sum(case((Establishment.status == EstablishmentStatus.SUSPENDU, 1), else_=0)),
        ).where(*_in_period(Establishment.created_at, start, end))
    )
    total, published, pending, rejected, suspended = result.one()
    return {
        "total": int(total or 0),
        "published": int(published or 0),
        "pending": int(pending or 0),
        "rejected": int(rejected or 0),
        "suspended": int(suspended or 0),
        "start_date": start_date,
        "end_date": end_date,
    }


async def get_stats_reservations(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start, end = _date_bounds(start_date, end_date)
    result = await session.execute(
        select(
            func.count(Reservation.id),
            func.sum(case((Reservation.status == ReservationStatus.EN_ATTENTE, 1), else_=0)),
            func.sum(case((Reservation.status == ReservationStatus.CONFIRMEE, 1), else_=0)),
            func.sum(case((Reservation.status == ReservationStatus.EN_COURS, 1), else_=0)),
            func.sum(case((Reservation.status == ReservationStatus.TERMINEE, 1), else_=0)),
            func.sum(case((Reservation.status == ReservationStatus.ANNULEE, 1), else_=0)),
            func.coalesce(func.sum(Reservation.total), ZERO),
        ).where(*_in_period(Reservation.created_at, start, end))
    )
    total, pending, confirmed, ongoing, completed, cancelled, value = result.one()
    return {
        "total": int(total or 0),
        "pending": int(pending or 0),
        "confirmed": int(confirmed or 0),
        "ongoing": int(ongoing or 0),
        "completed": int(completed or 0),
        "cancelled": int(cancelled or 0),
        "reservation_value": value or ZERO,
        "start_date": start_date,
        "end_date": end_date,
    }


async def get_stats_revenue(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start, end = _date_bounds(start_date, end_date)
    result = await session.execute(
        select(
            Transaction.currency,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), ZERO),
        )
        .where(
            Transaction.type == TransactionType.PAYMENT,
            Transaction.status == PaymentStatus.PAYE,
            *_in_period(Transaction.created_at, start, end),
        )
        .group_by(Transaction.currency)
        .order_by(Transaction.currency)
    )
    return {
        "currencies": [
            {"currency": currency, "payments": count, "gross_revenue": amount}
            for currency, count, amount in result.all()
        ],
        "start_date": start_date,
        "end_date": end_date,
    }


async def get_top_destinations(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 10,
) -> list[dict]:
    start, end = _date_bounds(start_date, end_date)
    result = await session.execute(
        select(
            Location.id,
            Location.name,
            Location.country_code,
            func.count(Reservation.id).label("reservation_count"),
        )
        .join(Establishment, Establishment.location_id == Location.id)
        .join(Reservation, Reservation.establishment_id == Establishment.id)
        .where(
            Location.is_active.is_(True),
            *_in_period(Reservation.created_at, start, end),
        )
        .group_by(Location.id, Location.name, Location.country_code)
        .order_by(func.count(Reservation.id).desc(), Location.id)
        .limit(limit)
    )
    return [
        {
            "location_id": location_id,
            "name": name,
            "country_code": country_code,
            "reservation_count": count,
        }
        for location_id, name, country_code, count in result.all()
    ]


async def get_top_establishments(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 10,
) -> list[dict]:
    start, end = _date_bounds(start_date, end_date)
    result = await session.execute(
        select(
            Establishment.id,
            Establishment.name,
            func.count(Reservation.id).label("reservation_count"),
            func.coalesce(
                func.sum(
                    case(
                        (Reservation.payment_status == PaymentStatus.PAYE, Reservation.total),
                        else_=ZERO,
                    )
                ),
                ZERO,
            ).label("gross_paid"),
        )
        .join(Reservation, Reservation.establishment_id == Establishment.id)
        .where(*_in_period(Reservation.created_at, start, end))
        .group_by(Establishment.id, Establishment.name)
        .order_by(func.count(Reservation.id).desc(), Establishment.id)
        .limit(limit)
    )
    return [
        {
            "establishment_id": establishment_id,
            "name": name,
            "reservation_count": count,
            "gross_paid": gross_paid,
        }
        for establishment_id, name, count, gross_paid in result.all()
    ]


async def get_recent_activities(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    result = await session.execute(
        select(ActivityLog)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "action": item.action,
            "description": item.description,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "created_at": item.created_at,
        }
        for item in result.scalars().all()
    ]


async def get_reservations_chart(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    period: ChartPeriod = "day",
) -> list[dict]:
    start, end = _date_bounds(start_date, end_date)
    bucket = func.date_trunc(period, Reservation.created_at).label("period")
    result = await session.execute(
        select(bucket, func.count(Reservation.id))
        .where(*_in_period(Reservation.created_at, start, end))
        .group_by(bucket)
        .order_by(bucket)
        .limit(2000)
    )
    return [
        {"period": point.isoformat(), "count": count}
        for point, count in result.all()
    ]


async def get_categories_chart(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    start, end = _date_bounds(start_date, end_date)
    result = await session.execute(
        select(Category.id, Category.name, func.count(Establishment.id))
        .outerjoin(Establishment, Establishment.category_id == Category.id)
        .where(*_in_period(Establishment.created_at, start, end))
        .group_by(Category.id, Category.name)
        .order_by(func.count(Establishment.id).desc(), Category.id)
        .limit(100)
    )
    return [
        {"category_id": category_id, "name": name, "count": count}
        for category_id, name, count in result.all()
    ]


async def get_revenue_chart(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    period: ChartPeriod = "day",
    currency: str = "XOF",
) -> list[dict]:
    start, end = _date_bounds(start_date, end_date)
    normalized_currency = currency.upper()
    if not normalized_currency.isascii() or not normalized_currency.isalpha():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Code devise invalide.",
        )

    bucket = func.date_trunc(period, Transaction.created_at).label("period")
    result = await session.execute(
        select(bucket, func.coalesce(func.sum(Transaction.amount), ZERO))
        .where(
            Transaction.type == TransactionType.PAYMENT,
            Transaction.status == PaymentStatus.PAYE,
            Transaction.currency == normalized_currency,
            *_in_period(Transaction.created_at, start, end),
        )
        .group_by(bucket)
        .order_by(bucket)
        .limit(2000)
    )
    return [
        {"period": point.isoformat(), "revenue": amount}
        for point, amount in result.all()
    ]

