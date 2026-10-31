import json
import secrets
import string
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from uuid import UUID
import logging


from fastapi import HTTPException, Request, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select
from app.config import settings

from app.models import (
    ActivityLog,
    Category,
    Establishment,
    Location,
    PlatformSetting,
    Reservation,
    SubCategory,
    Transaction,
    User,
)
from app.models.enums import (
    AvailabilityStatus,
    EstablishmentStatus,
    PaymentStatus,
    ReservationStatus,
    TransactionType,
)

from app.schemas.reservation import ReservationCreate
from app.models.notification import Notification
from app.models.enums import NotificationType
from app.services.notifi_dispatcher import dispatch_email
from app.emails import email as email_service

ZERO = Decimal("0.00")
MONEY_QUANTUM = Decimal("0.01")
ACTIVE_STATUSES = (
    ReservationStatus.EN_ATTENTE,
    ReservationStatus.CONFIRMEE,
    ReservationStatus.EN_COURS,
)
ALLOWED_TRANSITIONS = {
    ReservationStatus.EN_ATTENTE: {
        ReservationStatus.CONFIRMEE, ReservationStatus.REFUSEE,
        ReservationStatus.ANNULEE, ReservationStatus.EXPIREE,
    },
    ReservationStatus.CONFIRMEE: {
        ReservationStatus.EN_COURS, ReservationStatus.ANNULEE,
    },
    ReservationStatus.EN_COURS: {
        ReservationStatus.TERMINEE, ReservationStatus.ANNULEE,
    },
    ReservationStatus.TERMINEE: set(),
    ReservationStatus.REFUSEE: set(),
    ReservationStatus.ANNULEE: set(),
    ReservationStatus.EXPIREE: set(),
}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def get_pricing_rates(kind: str) -> dict[str, Decimal]:
    rates_by_category = {
        "hebergement": {
            "service_fee_percent": settings.SERVICE_FEE_PERCENT,
            "commission_percent": settings.COMMISSION_HEBERGEMENT_PERCENT,
            "tax_percent": settings.TAX_HEBERGEMENT_PERCENT,
        },
        "restaurant": {
            "service_fee_percent": settings.SERVICE_FEE_PERCENT,
            "commission_percent": settings.COMMISSION_RESTAURANT_PERCENT,
            "tax_percent": settings.TAX_RESTAURANT_PERCENT,
        },
        "loisir": {
            "service_fee_percent": settings.SERVICE_FEE_PERCENT,
            "commission_percent": settings.COMMISSION_LOISIR_PERCENT,
            "tax_percent": settings.TAX_LOISIR_PERCENT,
        },
    }

    if kind not in rates_by_category:
        raise ValueError(
            f"Catégorie non prise en charge : {kind}"
        )

    return rates_by_category[kind]


def money(value: Any) -> Decimal:
    try:
        result = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(409, "Un montant configuré est invalide.")
    if not result.is_finite():
        raise HTTPException(409, "Un montant configuré est invalide.")
    return result.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value)).upper()


def _category_name(establishment: Establishment) -> str:
    category = getattr(establishment, "category", None)
    values = [
        getattr(category, "name", None),
        getattr(category, "slug", None),
        getattr(category, "code", None),
    ]
    return " ".join(str(v).casefold() for v in values if v)


def _category_kind(establishment: Establishment) -> str:
    name = _category_name(establishment)
    if any(word in name for word in ("hebergement", "hébergement", "hotel", "hôtel", "logement", "accommodation")):
        return "hebergement"
    if any(word in name for word in ("restaurant", "restauration", "food")):
        return "restaurant"
    if any(word in name for word in ("loisir", "loisirs", "activite", "activité", "leisure", "experience")):
        return "loisir"
    # Fallback prudent basé sur l'unité de prix.
    unit = _enum_value(getattr(establishment, "price_unit", None))
    if unit in {"NUIT", "MOIS", "PERSONNE_NUIT"} or getattr(establishment, "price_per_night", None) is not None:
        return "hebergement"
    if unit in {"HEURE", "CRENEAU", "PRESTATION", "GROUPE"}:
        return "loisir"
    return "autre"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_reference() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "BR-" + "".join(secrets.choice(alphabet) for _ in range(10))


def _get_attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _model_fields(obj: Any) -> set[str]:

    mapper = getattr(obj, "__mapper__", None)

    if mapper is not None:
        return set(mapper.attrs.keys())

    table = getattr(obj, "__table__", None)
    if table is not None:
        return {column.key for column in table.columns}

    return set()


def _request_metadata(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:1000] or None
    return ip, ua


def audit_reservation(
    session: AsyncSession,
    actor: User | None,
    action: str,
    reservation: Reservation,
    request: Request | None = None,
    metadata: dict | None = None,
) -> None:
    ip, ua = _request_metadata(request)
    fields = _model_fields(ActivityLog)
    values = {
        "user_id": getattr(actor, "id", None),
        "action": action,
        "entity_type": "reservation",
        "entity_id": reservation.id,
        "ip_address": ip,
        "user_agent": ua,
        "metadata_json": metadata or {},
    }
    session.add(ActivityLog(**{k: v for k, v in values.items() if k in fields}))


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflit de données : la réservation a peut-être déjà été créée. Rechargez vos réservations.",
        )


def _http_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


# ---------------------------------------------------------------------------
# Établissements réservables
# ---------------------------------------------------------------------------

def public_establishment_query(establishment_id: UUID | None = None):
    statement = (
        select(Establishment)
        .join(Category, Category.id == Establishment.category_id)
        .outerjoin(SubCategory, SubCategory.id == Establishment.subcategory_id)
        .join(Location, Location.id == Establishment.location_id)
        .options(selectinload(Establishment.category))
        .where(
            Establishment.status == EstablishmentStatus.PUBLIE,
            Location.is_active.is_(True),
        )
    )
    if establishment_id is not None:
        statement = statement.where(Establishment.id == establishment_id)
    return statement


async def get_bookable_establishment(
    establishment_id: UUID,
    session: AsyncSession,
    *,
    for_update: bool = False,
) -> Establishment:
    statement = public_establishment_query(establishment_id)
    if for_update:
        statement = statement.with_for_update(of=Establishment)
    result = await session.execute(statement)
    establishment = result.scalars().first()
    if not establishment:
        raise _http_error(404, "Établissement public introuvable.")
    if establishment.availability_status != AvailabilityStatus.AVAILABLE:
        raise _http_error(409, "Cet établissement n'est pas disponible à la réservation.")
    return establishment


# ---------------------------------------------------------------------------
# Validation des dates et tarification
# ---------------------------------------------------------------------------

def validate_dates(start_date: date, end_date: date) -> int:
    if start_date < date.today():
        raise _http_error(422, "La date de début ne peut pas être passée.")
    days = (end_date - start_date).days
    if days <= 0:
        raise _http_error(422, "La date de fin doit être postérieure à la date de début.")
    if days > 730:
        raise _http_error(422, "La réservation ne peut pas dépasser deux ans.")
    return days


def _months_covered(start_date: date, end_date: date) -> int:
    months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
    if end_date.day > start_date.day:
        months += 1
    return max(1, months)


def _validate_booking_period(
    establishment: Establishment,
    start_date: date,
    end_date: date | None,
    start_time: time | None = None,
    end_time: time | None = None,
) -> tuple[str, int]:
    kind = _category_kind(establishment)
    if start_date < date.today():
        raise _http_error(422, "La date de début ne peut pas être passée.")
    if kind == "hebergement":
        if end_date is None:
            raise _http_error(422, "La date de départ est obligatoire pour un hébergement.")
        return kind, validate_dates(start_date, end_date)
    if kind == "restaurant" and end_date is not None and end_date != start_date:
        raise _http_error(422, "Une réservation de restaurant ne nécessite pas de date de départ ; utilisez le créneau horaire.")
    if end_date is not None:
        if end_date < start_date:
            raise _http_error(422, "La date de fin ne peut pas précéder la date de début.")
        if end_date != start_date:
            validate_dates(start_date, end_date)
    unit = _enum_value(getattr(establishment, "price_unit", None))
    if kind in {"restaurant", "loisir"} and unit in {"HEURE", "CRENEAU"}:
        if start_time is None or end_time is None:
            raise _http_error(422, "L'heure de début et l'heure de fin sont obligatoires.")
        if end_time <= start_time:
            raise _http_error(422, "L'heure de fin doit être postérieure à l'heure de début.")
    return kind, 1 if end_date is None or end_date == start_date else (end_date - start_date).days

def calculate_quote(
    establishment: Establishment,
    *,
    start_date: date,
    end_date: date | None,
    quantity: int,
    adults: int,
    children: int,
    service_fee_percent: Decimal | None = None,
    commission_percent: Decimal | None = None,
    tax_percent: Decimal | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    options: dict | None = None,
) -> dict:
    """
    Calcule un devis BestRev selon la catégorie et l'unité tarifaire.

    Politique tarifaire :
    - Frais de service : taux fixe configuré dans .env.
    - Commission : taux fixe selon la catégorie.
    - Taxe : taux fixe selon la catégorie.
    - La taxe est calculée séparément et n'est pas ajoutée au total client.
    - Les tarifs et les prix des options proviennent du serveur.
    """

    # ---------------------------------------------------------
    # 1. Validation des quantités
    # ---------------------------------------------------------

    if quantity < 1 or adults < 0 or children < 0:
        raise _http_error(
            422,
            "Les quantités et le nombre de personnes sont invalides.",
        )

    kind, days = _validate_booking_period(
        establishment,
        start_date,
        end_date,
        start_time,
        end_time,
    )

    guests = adults + children

    if guests < 1:
        raise _http_error(
            422,
            "La réservation doit concerner au moins une personne.",
        )

    # ---------------------------------------------------------
    # 2. Récupération des taux fixes depuis .env
    # ---------------------------------------------------------

    rates_by_category = {
        "hebergement": {
            "service_fee_percent": settings.SERVICE_FEE_PERCENT,
            "commission_percent": settings.COMMISSION_HEBERGEMENT_PERCENT,
            "tax_percent": settings.TAX_HEBERGEMENT_PERCENT,
        },
        "restaurant": {
            "service_fee_percent": settings.SERVICE_FEE_PERCENT,
            "commission_percent": settings.COMMISSION_RESTAURANT_PERCENT,
            "tax_percent": settings.TAX_RESTAURANT_PERCENT,
        },
        "loisir": {
            "service_fee_percent": settings.SERVICE_FEE_PERCENT,
            "commission_percent": settings.COMMISSION_LOISIR_PERCENT,
            "tax_percent": settings.TAX_LOISIR_PERCENT,
        },
    }

    if kind not in rates_by_category:
        raise _http_error(
            422,
            f"Catégorie non prise en charge : {kind}.",
        )

    configured_rates = rates_by_category[kind]

    # Les valeurs fournies par le service appelant restent possibles.
    # En leur absence, les taux de .env sont utilisés.
    fee_rate = (
        configured_rates["service_fee_percent"]
        if service_fee_percent is None
        else service_fee_percent
    )

    commission_rate = (
        configured_rates["commission_percent"]
        if commission_percent is None
        else commission_percent
    )

    tax_rate = (
        configured_rates["tax_percent"]
        if tax_percent is None
        else tax_percent
    )

    # ---------------------------------------------------------
    # 3. Vérification de l'unité tarifaire
    # ---------------------------------------------------------

    unit_name = _enum_value(
        getattr(establishment, "price_unit", None)
    )

    allowed_units = {
        "hebergement": {
            "NUIT",
            "PERSONNE_NUIT",
            "PERSONNE",
            "MOIS",
        },
        "restaurant": {
            "PERSONNE",
            "GROUPE",
            "PRESTATION",
            "CRENEAU",
        },
        "loisir": {
            "PERSONNE",
            "GROUPE",
            "PRESTATION",
            "HEURE",
            "CRENEAU",
        },
    }

    if unit_name not in allowed_units[kind]:
        if unit_name not in {"NONE", ""}:
            raise _http_error(
                409,
                (
                    f"L'unité tarifaire {unit_name} "
                    f"n'est pas valide pour la catégorie {kind}."
                ),
            )

        unit_name = {
            "hebergement": "NUIT",
            "restaurant": "PERSONNE",
            "loisir": "PRESTATION",
        }[kind]

    if kind == "hebergement" and end_date is None:
        raise _http_error(
            422,
            "La date de départ est obligatoire pour un hébergement.",
        )

    # ---------------------------------------------------------
    # 4. Calcul des unités et récupération du prix
    # ---------------------------------------------------------

    if unit_name == "NUIT":
        unit_price_raw = _get_attr(
            establishment,
            "price_per_night",
            "price",
        )
        units = Decimal(days * quantity)
        unit_label = "nuit_chambre"

    elif unit_name == "PERSONNE_NUIT":
        unit_price_raw = _get_attr(
            establishment,
            "price_per_night",
            "price",
        )
        units = Decimal(days * guests)
        unit_label = "personne_nuit"

    elif unit_name == "MOIS":
        unit_price_raw = _get_attr(
            establishment,
            "price_per_month",
            "price",
        )
        months = (
            _months_covered(start_date, end_date)
            if end_date
            else 1
        )
        units = Decimal(months * quantity)
        unit_label = "mois"

    elif unit_name == "PERSONNE":
        unit_price_raw = _get_attr(establishment, "price")
        units = Decimal(guests)
        unit_label = "personne"

    elif unit_name == "GROUPE":
        unit_price_raw = _get_attr(establishment, "price")
        units = Decimal(quantity)
        unit_label = "groupe"

    elif unit_name == "PRESTATION":
        unit_price_raw = _get_attr(establishment, "price")
        units = Decimal(quantity)
        unit_label = "prestation"

    elif unit_name == "HEURE":
        unit_price_raw = _get_attr(establishment, "price")

        if start_time is None or end_time is None:
            raise _http_error(
                422,
                "Les heures de début et de fin sont obligatoires.",
            )

        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        duration_minutes = end_minutes - start_minutes

        if duration_minutes <= 0:
            raise _http_error(
                422,
                "La durée doit être positive et ne peut pas traverser minuit.",
            )

        units = (
            Decimal(duration_minutes)
            / Decimal("60")
            * Decimal(quantity)
        )
        unit_label = "heure"

    elif unit_name == "CRENEAU":
        unit_price_raw = _get_attr(establishment, "price")
        units = Decimal(quantity)
        unit_label = "créneau"

    else:
        raise _http_error(
            409,
            "L'unité tarifaire de cet établissement est invalide.",
        )

    if unit_price_raw is None:
        raise _http_error(
            409,
            "Le tarif requis n'est pas configuré pour cet établissement.",
        )

    try:
        unit_price = money(unit_price_raw)
    except (InvalidOperation, TypeError, ValueError):
        raise _http_error(
            409,
            "Le tarif configuré est invalide.",
        )

    if not unit_price.is_finite() or unit_price < ZERO:
        raise _http_error(
            409,
            "Le tarif doit être positif ou nul.",
        )

    # ---------------------------------------------------------
    # 5. Calcul du sous-total de base
    # ---------------------------------------------------------

    base_subtotal = money(unit_price * units)

    # ---------------------------------------------------------
    # 6. Calcul des options configurées côté serveur
    # ---------------------------------------------------------

    options = options or {}

    if not isinstance(options, dict):
        raise _http_error(
            422,
            "Les options doivent être un objet JSON valide.",
        )

    configured_options = (
        _get_attr(establishment, "pricing_options", default={}) or {}
    )

    if not isinstance(configured_options, dict):
        configured_options = {}

    options_total = ZERO
    options_breakdown: list[dict] = []

    for option_key, option_quantity in options.items():
        if option_key not in configured_options:
            raise _http_error(
                422,
                f"L'option {option_key} n'est pas tarifée pour cet établissement.",
            )

        try:
            option_qty = Decimal(
                str(
                    option_quantity
                    if option_quantity is not None
                    else 1
                )
            )
            option_price = money(configured_options[option_key])

        except (InvalidOperation, TypeError, ValueError):
            raise _http_error(
                422,
                f"Quantité ou tarif invalide pour l'option {option_key}.",
            )

        if (
            not option_qty.is_finite()
            or option_qty < ZERO
            or option_qty > Decimal("1000")
            or not option_price.is_finite()
            or option_price < ZERO
        ):
            raise _http_error(
                422,
                f"Quantité ou tarif invalide pour l'option {option_key}.",
            )

        line_total = money(option_price * option_qty)
        options_total += line_total

        options_breakdown.append({
            "key": str(option_key),
            "quantity": str(option_qty),
            "unit_price": str(option_price),
            "total": str(line_total),
        })

    options_total = money(options_total)
    subtotal = money(base_subtotal + options_total)

    # ---------------------------------------------------------
    # 7. Validation des taux
    # ---------------------------------------------------------

    def validate_percent(
        value: Decimal,
        label: str,
        maximum: Decimal = Decimal("100"),
    ) -> Decimal:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise _http_error(
                503,
                f"Le taux {label} est invalide.",
            )

        if (
            not parsed.is_finite()
            or parsed < ZERO
            or parsed > maximum
        ):
            raise _http_error(
                503,
                f"Le taux {label} doit être compris entre 0 et {maximum} %.",
            )

        return parsed

    fee_rate = validate_percent(
        fee_rate,
        "des frais de service",
        Decimal("30"),
    )

    commission_rate = validate_percent(
        commission_rate,
        "de commission",
    )

    tax_rate = validate_percent(
        tax_rate,
        "de taxe",
    )

    # ---------------------------------------------------------
    # 8. Frais de service
    # ---------------------------------------------------------

    service_fee = money(
        subtotal * fee_rate / Decimal("100")
    )

    # ---------------------------------------------------------
    # 9. Taxe calculée séparément
    # ---------------------------------------------------------

    tax_amount = money(
        subtotal * tax_rate / Decimal("100")
    )

    # Les réductions doivent être validées côté serveur.
    discount_amount = ZERO

    # La taxe n'est pas ajoutée au montant demandé au client.
    total = money(
        subtotal + service_fee - discount_amount
    )

    # ---------------------------------------------------------
    # 10. Commission et part du partenaire
    # ---------------------------------------------------------

    commission_amount = money(
        subtotal * commission_rate / Decimal("100")
    )

    # Part calculée avant tout ajustement fiscal.
    partner_amount = money(
        max(ZERO, subtotal - commission_amount)
    )

    # ---------------------------------------------------------
    # 11. Résultat du devis
    # ---------------------------------------------------------

    return {
        "establishment_id": establishment.id,
        "category_kind": kind,
        "start_date": start_date,
        "end_date": end_date,
        "start_time": start_time,
        "end_time": end_time,
        "nights": days if kind == "hebergement" else None,
        "quantity": quantity,
        "adults": adults,
        "children": children,
        "unit_price": unit_price,
        "price_unit": unit_name,
        "unit_label": unit_label,
        "price_units": units,
        "base_subtotal": base_subtotal,
        "options_total": options_total,
        "options_breakdown": options_breakdown,
        "subtotal": subtotal,
        "service_fee_percent": fee_rate,
        "service_fee": service_fee,
        "tax_percent": tax_rate,
        "tax_amount": tax_amount,
        "discount_amount": discount_amount,
        "total": total,
        "commission_rate": commission_rate,
        "commission_amount": commission_amount,
        "partner_amount": partner_amount,
        "currency": getattr(establishment, "currency", None) or "XOF",
    }
   
async def configured_service_fee_percent(session: AsyncSession) -> Decimal:
    result = await session.execute(
        select(PlatformSetting.value, PlatformSetting.value_json).where(
            PlatformSetting.key == "service_fee_percent"
        )
    )
    row = result.first()
    if not row:
        return ZERO
    value, value_json = row
    raw = value_json if value_json is not None else value
    if raw is None:
        return ZERO
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        percent = Decimal(str(parsed))
    except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError):
        raise _http_error(503, "Le taux de frais configuré est invalide.")
    if not percent.is_finite() or percent < 0 or percent > 30:
        raise _http_error(503, "Le taux de frais configuré est invalide.")
    return percent


async def configured_percent(session: AsyncSession, keys: list[str], *, maximum: Decimal = Decimal("100")) -> Decimal:
    """Lit le premier taux configuré. Les taux absents valent zéro."""
    for key in keys:
        result = await session.execute(
            select(PlatformSetting.value, PlatformSetting.value_json).where(PlatformSetting.key == key)
        )
        row = result.first()
        if not row:
            continue
        value, value_json = row
        raw = value_json if value_json is not None else value
        if raw is None:
            continue
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            rate = Decimal(str(parsed))
        except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError):
            raise _http_error(503, f"Le paramètre {key} est invalide.")
        if not rate.is_finite() or rate < 0 or rate > maximum:
            raise _http_error(503, f"Le paramètre {key} doit être compris entre 0 et {maximum} %.")
        return rate
    return ZERO


async def configured_commission_percent(session: AsyncSession, establishment: Establishment, kind: str) -> Decimal:
    # Priorité : taux contractualisé sur l'établissement, puis configuration
    # par catégorie, puis taux global de la plateforme.
    local_rate = _get_attr(establishment, "commission_rate", "commission_percent")
    if local_rate is not None:
        try:
            value = Decimal(str(local_rate))
        except (InvalidOperation, TypeError, ValueError):
            raise _http_error(503, "Le taux de commission de l'établissement est invalide.")
        if not value.is_finite() or value < 0 or value > 100:
            raise _http_error(503, "Le taux de commission doit être compris entre 0 et 100 %.")
        return value
    return await configured_percent(
        session,
        [f"commission_percent_{kind}", "commission_percent"],
        maximum=Decimal("100"),
    )


# ---------------------------------------------------------------------------
# Disponibilité et capacité
# ---------------------------------------------------------------------------

async def capacity_state(
    establishment: Establishment,
    start_date: date,
    end_date: date | None,
    session: AsyncSession,
    *,
    start_time: time | None = None,
    end_time: time | None = None,
    exclude_reservation_id: UUID | None = None,
) -> tuple[int, int, int | None]:
    statement = select(
        func.coalesce(func.sum(Reservation.quantity), 0),
        func.coalesce(func.sum(Reservation.adults + Reservation.children), 0),
        func.count(Reservation.id),
    ).where(
        Reservation.establishment_id == establishment.id,
        Reservation.status.in_(ACTIVE_STATUSES),
    )
    is_stay = _category_kind(establishment) == "hebergement" or (
        end_date is not None and end_date > start_date
    )
    if is_stay:
        statement = statement.where(
            or_(Reservation.start_date.is_(None), Reservation.start_date < (end_date or start_date)),
            or_(Reservation.end_date.is_(None), Reservation.end_date > start_date),
        )
    else:
        statement = statement.where(Reservation.start_date == start_date)
        if start_time is not None and end_time is not None:
            statement = statement.where(
                or_(Reservation.start_time.is_(None), Reservation.start_time < end_time),
                or_(Reservation.end_time.is_(None), Reservation.end_time > start_time),
            )
    if exclude_reservation_id is not None:
        statement = statement.where(Reservation.id != exclude_reservation_id)
    result = await session.execute(statement)
    reserved_units, reserved_guests, count = result.one()
    reserved_units, reserved_guests = int(reserved_units), int(reserved_guests)

    capacities = []
    if establishment.rooms_count is not None:
        capacities.append(max(0, establishment.rooms_count - reserved_units))
    if establishment.capacity is not None:
        capacities.append(max(0, establishment.capacity - reserved_guests))
    if not capacities:
        capacities.append(max(0, 1 - reserved_units))
    return reserved_units, reserved_guests, min(capacities)


async def check_capacity(
    establishment: Establishment,
    *,
    start_date: date,
    end_date: date | None,
    quantity: int,
    adults: int,
    children: int,
    session: AsyncSession,
    start_time: time | None = None,
    end_time: time | None = None,
    exclude_reservation_id: UUID | None = None,
) -> int | None:
    if establishment.availability_status != AvailabilityStatus.AVAILABLE:
        raise _http_error(409, "L'établissement n'est pas disponible à la réservation.")
    reserved_units, reserved_guests, remaining = await capacity_state(
        establishment, start_date, end_date, session,
        start_time=start_time, end_time=end_time,
        exclude_reservation_id=exclude_reservation_id,
    )
    if establishment.rooms_count is not None and reserved_units + quantity > establishment.rooms_count:
        raise _http_error(409, "Le nombre d'unités demandé dépasse la capacité restante.")
    guests = adults + children
    if establishment.capacity is not None and reserved_guests + guests > establishment.capacity:
        raise _http_error(409, "La capacité restante est insuffisante pour le nombre de personnes demandé.")
    if establishment.rooms_count is None and establishment.capacity is None and reserved_units + quantity > 1:
        raise _http_error(409, "Une réservation existe déjà pour cette période.")
    if establishment.capacity is not None and guests > establishment.capacity:
        raise _http_error(422, "Le nombre de personnes dépasse la capacité totale.")
    if establishment.rooms_count is not None and quantity > establishment.rooms_count:
        raise _http_error(422, "Le nombre d'unités dépasse la capacité totale.")
    return remaining


async def check_establishment_availability(
    establishment_id: UUID,
    start_date: date,
    session: AsyncSession,
    end_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    quantity: int = 1,
    adults: int = 1,
    children: int = 0,
) -> dict:
    establishment = await get_bookable_establishment(establishment_id, session)
    kind, _ = _validate_booking_period(establishment, start_date, end_date, start_time, end_time)
    if kind == "hebergement" and end_date is None:
        raise _http_error(422, "La date de départ est obligatoire pour un hébergement.")
    remaining = await check_capacity(
        establishment, start_date=start_date, end_date=end_date, quantity=quantity,
        adults=adults, children=children, session=session,
        start_time=start_time, end_time=end_time,
    )
    return {
        "establishment_id": establishment.id,
        "available": remaining is None or remaining >= quantity,
        "availability_status": establishment.availability_status,
        "start_date": start_date,
        "end_date": end_date,
        "start_time": start_time,
        "end_time": end_time,
        "remaining_capacity": remaining,
    }


async def reservation_quote(
    data: ReservationCreate,
    session: AsyncSession,
    *,
    exclude_reservation_id: UUID | None = None,
    for_update: bool = False,
) -> tuple[Establishment, dict]:
    establishment = await get_bookable_establishment(
        data.establishment_id, session, for_update=for_update
    )
    kind, _ = _validate_booking_period(
        establishment,
        data.start_date,
        getattr(data, "end_date", None),
        getattr(data, "start_time", None),
        getattr(data, "end_time", None),
    )
    
    rates = get_pricing_rates(kind)

    quote = calculate_quote(
    establishment,
    start_date=data.start_date,
    end_date=getattr(data, "end_date", None),
    quantity=data.quantity,
    adults=data.adults,
    children=data.children,
    service_fee_percent=rates["service_fee_percent"],
    commission_percent=rates["commission_percent"],
    tax_percent=rates["tax_percent"],
    start_time=getattr(data, "start_time", None),
    end_time=getattr(data, "end_time", None),
    options=getattr(data, "options", None),
) 
    
    await check_capacity(
        establishment,
        start_date=data.start_date,
        end_date=getattr(data, "end_date", None),
        quantity=data.quantity,
        adults=data.adults,
        children=data.children,
        session=session,
        start_time=getattr(data, "start_time", None),
        end_time=getattr(data, "end_time", None),
        
    )
    return establishment, quote


# ---------------------------------------------------------------------------
# Accès et idempotence
# ---------------------------------------------------------------------------

async def get_client_reservation(
    reservation_id: UUID,
    user_id: UUID,
    session: AsyncSession,
    *,
    for_update: bool = False
) -> Reservation:
    stmt = (
        select(Reservation)
        .options(selectinload(Reservation.establishment))
        .where(
            Reservation.id == reservation_id,
            Reservation.user_id == user_id
        )
    )

    if for_update:
        stmt = stmt.with_for_update()

    result = await session.execute(stmt)
    reservation = result.scalars().first()

    if not reservation:
        raise _http_error(404, "Réservation introuvable.")

    return reservation


async def get_admin_reservation(
    reservation_id: UUID, session: AsyncSession, *, for_update: bool = False
) -> Reservation:
    stmt = (
    select(Reservation)
    .options(selectinload(Reservation.establishment))
    .where(Reservation.id == reservation_id)
)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    reservation = result.scalars().first()
    if not reservation:
        raise _http_error(404, "Réservation introuvable.")
    return reservation


async def has_pending_fedapay_payment(reservation_id: UUID, session: AsyncSession) -> bool:
    result = await session.execute(
        select(Transaction.id).where(
            Transaction.reservation_id == reservation_id,
            Transaction.type == TransactionType.PAYMENT,
            Transaction.provider == "FEDAPAY",
            Transaction.status == PaymentStatus.EN_ATTENTE,
        ).limit(1)
    )
    return result.first() is not None


async def _find_idempotent(
    session: AsyncSession, user_id: UUID, key: str
) -> Reservation | None:
    result = await session.execute(
        select(Reservation).where(
            Reservation.user_id == user_id,
            Reservation.idempotency_key == key,
        )
    )
    return result.scalars().first()


def _snapshot(quote: dict, establishment: Establishment) -> dict:
    money_keys = (
        "unit_price", "base_subtotal", "options_total", "subtotal",
        "service_fee_percent", "service_fee", "tax_percent", "tax_amount",
        "discount_amount", "total", "commission_rate", "commission_amount",
        "partner_amount",
    )
    snapshot = {
        key: str(quote[key]) for key in money_keys if key in quote
    }
    snapshot.update({
        "category_kind": quote.get("category_kind"),
        "price_unit": quote.get("price_unit"),
        "unit_label": quote.get("unit_label"),
        "price_units": str(quote.get("price_units", "0")),
        "nights": quote.get("nights"),
        "quantity": quote.get("quantity"),
        "adults": quote.get("adults"),
        "children": quote.get("children"),
        "options_breakdown": quote.get("options_breakdown", []),
        "currency": quote.get("currency"),
        "establishment_name": getattr(establishment, "name", None),
        "calculated_at": _now_utc().isoformat(),
    })
    return snapshot



def _client_snapshot(user: User) -> dict:
    profile = getattr(user, "profile", None)
    first = _get_attr(profile, "first_name", "firstname", "firstName", "prenom", default="")
    last = _get_attr(profile, "last_name", "lastname", "lastName", "nom", default="")
    email = getattr(user, "email", None)
    phone = _get_attr(profile, "phone", "phone_number", "telephone", "tel", default="")
    return {
        "client_first_name": str(first or ""),
        "client_last_name": str(last or ""),
        "client_email": str(email or ""),
        "client_phone": str(phone or ""),
    }


def _reservation_values(
    data: Any,
    user: User,
    establishment: Establishment,
    quote: dict,
    idempotency_key: str | None,
) -> dict:
    """Prépare les données de réservation à enregistrer."""

    if user.id is None:
        raise _http_error(
            401,
            "Impossible d'identifier le client connecté.",
        )

    values = {
        "reference": _new_reference(),
        "idempotency_key": idempotency_key,
        "user_id": user.id,
        "establishment_id": establishment.id,
        "category": getattr(establishment.category, "name", None),
        "reservation_date": date.today(),
        "start_date": data.start_date,
        "end_date": getattr(data, "end_date", None),
        "start_time": getattr(data, "start_time", None),
        "end_time": getattr(data, "end_time", None),
        "quantity": data.quantity,
        "nights": quote.get("nights"),
        "adults": data.adults,
        "children": data.children,
        "room_or_unit": getattr(data, "room_or_unit", None),
        "options": getattr(data, "options", None) or {},
        "special_requests": getattr(data, "special_requests", None),
        **_client_snapshot(user),
        "pricing_snapshot": _snapshot(quote, establishment),
        "subtotal": quote["subtotal"],
        "service_fee": quote["service_fee"],
        "tax_amount": quote["tax_amount"],
        "discount_amount": quote["discount_amount"],
        "total": quote["total"],
        "currency": quote["currency"],
        "commission_rate": quote.get("commission_rate", ZERO),
        "commission_amount": quote.get("commission_amount", ZERO),
        "partner_amount": quote.get(
            "partner_amount",
            quote["subtotal"],
        ),
        "payment_method": getattr(data, "payment_method", None),
        "payment_status": PaymentStatus.EN_ATTENTE,
        "status": ReservationStatus.EN_ATTENTE,
        "amount_paid": ZERO,
        "balance_due": quote["total"],
    }

    model_fields = _model_fields(Reservation)

    filtered_values = {
        key: value
        for key, value in values.items()
        if key in model_fields
    }

    # Vérifier que le client possède un identifiant valide.
    if user.id is None:
        raise _http_error(
            401,
            "Impossible d'identifier le client connecté.",
        )

    # Vérifier que le modèle reconnaît user_id.
    if "user_id" not in model_fields:
        logger.error(
            "user_id absent des attributs du modèle Reservation : %s",
            model_fields,
        )
        raise RuntimeError(
            "Le modèle Reservation ne reconnaît pas le champ user_id."
        )

    # Affecter explicitement l'identifiant du client.
    filtered_values["user_id"] = user.id

    logger.info(
        "Création réservation : user.id=%s, values.user_id=%s",
        user.id,
        filtered_values["user_id"],
    )

    return filtered_values

# ---------------------------------------------------------------------------
# Consultation client / administration
# ---------------------------------------------------------------------------

def _apply_filters(stmt, *, status_filter=None, establishment_id=None, user_id=None, start_date=None, end_date=None):
    if status_filter is not None:
        stmt = stmt.where(Reservation.status == status_filter)
    if establishment_id is not None:
        stmt = stmt.where(Reservation.establishment_id == establishment_id)
    if user_id is not None:
        stmt = stmt.where(Reservation.user_id == user_id)
    if start_date is not None:
        stmt = stmt.where(Reservation.start_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Reservation.start_date <= end_date)
    return stmt


async def list_client_reservations(
    user_id: UUID,
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter=None,
    status=None,
):
    # 1. Normaliser les paramètres de pagination
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    # 2. Déterminer le statut à appliquer
    selected_status = (
        status_filter
        if status_filter is not None
        else status
    )

    # 3. Construire la requête de base
    base = _apply_filters(
    select(Reservation)
    .options(
        selectinload(Reservation.establishment)
    )
    .where(
        Reservation.user_id == user_id
    ),
    status_filter=selected_status,
    )

    # 4. Compter le nombre total de réservations
    count_stmt = select(
        func.count()
    ).select_from(
        base.order_by(None).subquery()
    )

    total = await session.scalar(count_stmt)
    total = int(total or 0)

    # 5. Calculer l'offset
    offset = (page - 1) * page_size

    # 6. Récupérer les réservations de la page demandée
    order_column = (
        Reservation.created_at
        if hasattr(Reservation, "created_at")
        else Reservation.start_date
    )

    stmt = (
        base
        .order_by(order_column.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await session.execute(stmt)
    items = result.scalars().all()

    # 7. Retourner une réponse conforme à ReservationPage
    return {
        "items": items,
        "total": total,
        "limit": page_size,
        "offset": offset,
    }

async def get_client_reservation_by_reference(
    reference: str,
    user_id: UUID,
    session: AsyncSession
) -> Reservation:
    stmt = (
        select(Reservation)
        .options(selectinload(Reservation.establishment))
        .where(
            Reservation.reference == reference,
            Reservation.user_id == user_id
        )
    )

    result = await session.execute(stmt)
    reservation = result.scalars().first()

    if reservation is None:
        raise _http_error(404, "Réservation introuvable.")

    return reservation

async def list_admin_reservations(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter=None,
    status=None,
    establishment_id: UUID | None = None,
    user_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
):
    # Normalisation de la pagination
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    selected_status = (
        status_filter
        if status_filter is not None
        else status
    )

    # Requête de base avec les filtres
    base = _apply_filters(
        select(Reservation).options(
            selectinload(Reservation.establishment)
        ),
        status_filter=selected_status,
        establishment_id=establishment_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )
    # Recherche par référence, email ou téléphone
    if search and search.strip():
        term = f"%{search.strip()}%"

        conditions = [
            Reservation.reference.ilike(term)
        ]

        if hasattr(Reservation, "client_email"):
            conditions.append(
                Reservation.client_email.ilike(term)
            )

        if hasattr(Reservation, "client_phone"):
            conditions.append(
                Reservation.client_phone.ilike(term)
            )

        base = base.where(or_(*conditions))

    # Compter le nombre total de résultats filtrés
    total = await session.scalar(
        select(func.count()).select_from(
            base.subquery()
        )
    )

    total = int(total or 0)

    # Récupérer la page demandée
    sort_field = getattr(
        Reservation,
        "created_at",
        Reservation.start_date,
    )

    result = await session.execute(
        base.order_by(sort_field.desc())
        .offset(offset)
        .limit(page_size)
    )

    items = result.scalars().all()

    # Respecter exactement AdminReservationPage
    return {
        "items": items,
        "total": total,
        "limit": page_size,
        "offset": offset,
    }

# ---------------------------------------------------------------------------
# Modification, annulation, transitions admin
# ---------------------------------------------------------------------------

async def create_client_reservation(
    data: ReservationCreate,
    current_user: User,
    session: AsyncSession,
    request: Request,
    idempotency_key: str | None = None,
) -> Reservation:
 
    if not data.establishment_id:
        raise _http_error(
            422,
            "L'identifiant de l'établissement est obligatoire.",
        )

    # 2. Valider la clé d'idempotence
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()

        if not idempotency_key:
            idempotency_key = None

    if idempotency_key and len(idempotency_key) > 255:
        raise _http_error(
            422,
            "La clé d'idempotence ne doit pas dépasser 255 caractères.",
        )

    # 3. Vérifier si cette réservation existe déjà
    if idempotency_key:
        existing = await _find_idempotent(
            session,
            current_user.id,
            idempotency_key,
        )

        if existing:
            if existing.establishment_id != data.establishment_id:
                raise _http_error(
                    409,
                    (
                        "Cette clé d'idempotence a déjà été utilisée "
                        "pour une autre réservation."
                    ),
                )

            # Une nouvelle requête avec la même clé retourne
            # la réservation existante sans créer de doublon.
            return existing

    try:
        # 4. Vérifier l'établissement et calculer le devis.
        # Le verrouillage doit être appliqué dans reservation_quote()
        # pour protéger les vérifications de disponibilité.
        establishment, quote = await reservation_quote(
            data,
            session,
            for_update=True,
        )

        # 5. Construire les valeurs à enregistrer.
        # Cette fonction doit notamment conserver le snapshot
        # tarifaire utilisé lors de la création.
        values = _reservation_values(
            data,
            current_user,
            establishment,
            quote,
            idempotency_key,
        )

                # 6. Créer la réservation
        logger.info("current_user.id = %s", current_user.id)
        logger.info("values['user_id'] = %s", values.get("user_id"))

        if current_user.id is None or values.get("user_id") is None:
            raise _http_error(
                401,
                "L'identifiant du client est manquant.",
            )

        reservation = Reservation(**values)

        session.add(reservation)

        # Exécuter les INSERT avant de poursuivre.
        await session.flush()

        # 7. Enregistrer l'événement d'audit
        audit_reservation(
            session,
            current_user,
            "reservation.created",
            reservation,
            request,
            {
                "total": str(quote["total"]),
                "currency": quote["currency"],
            },
        )

                # Notification interne : demande de réservation créée.
        await _add_internal_notification(
            session=session,
            user_id=current_user.id,
            event="reservation_created",
            title="Demande de réservation créée",
            message=(
                f"Votre demande {reservation.reference} a été créée. "
                "Vous serez informé de son évolution."
            ),
            action_url="/pages/front-office/reservations",
        )

        # 8. Valider la transaction
        await session.commit()

        # 9. Recharger les données persistées
        await session.refresh(reservation)
        
        # Email envoyé uniquement après la validation de la transaction.
        _send_reservation_email(
            event="reservation.created",
            sender=email_service.send_reservation_created_email,
            reservation=reservation,
            name=_reservation_client_name(reservation),
            reservation_reference=reservation.reference,
            establishment_name=_reservation_establishment_name(
                reservation,
                establishment,
            ),
            start_date=reservation.start_date,
            end_date=reservation.end_date,
            amount=reservation.total,
        )

        return reservation

    except IntegrityError as exc:
        await session.rollback()

        # Afficher l'erreur réelle dans le terminal
        logger.exception(
            "Erreur d'intégrité lors de la création "
            "de la réservation : %s",
            exc.orig,
        )

        # Vérifier si une requête concurrente a créé
        # la réservation avec la même clé d'idempotence.
        if idempotency_key:
            existing = await _find_idempotent(
                session,
                current_user.id,
                idempotency_key,
            )

            if existing:
                if existing.establishment_id != data.establishment_id:
                    raise _http_error(
                        409,
                        (
                            "Cette clé d'idempotence a déjà été utilisée "
                            "pour une autre réservation."
                        ),
                    )

                return existing

        # Message temporaire pour faciliter le diagnostic
        raise _http_error(
            409,
            f"Échec de création de la réservation : {str(exc.orig)}",
        ) from exc

    except Exception:
        await session.rollback()
        raise


async def cancel_client_reservation(
    reservation_id: UUID, user_id: UUID, session: AsyncSession,
    request: Request | None = None, reason: str | None = None,
) -> Reservation:
    reservation = await get_client_reservation(reservation_id, user_id, session, for_update=True)

    if reservation.status not in {ReservationStatus.EN_ATTENTE, ReservationStatus.CONFIRMEE}:
        raise _http_error(409, "Cette réservation ne peut plus être annulée par le client.")
    
    if (reservation.amount_paid or ZERO) > ZERO:
        # Pas de remboursement automatique : la politique doit être vérifiée par l'administration.
        raise _http_error(409, "Un paiement a déjà été enregistré. Contactez BestRev pour traiter l'annulation et le remboursement.")
    
    reservation.status = ReservationStatus.ANNULEE
    reservation.cancelled_at = _now_utc().replace(tzinfo=None)
    reservation.cancellation_reason = (reason or "").strip() or None
    audit_reservation(session, None, "reservation.cancelled_by_client", reservation, request, {"reason": reservation.cancellation_reason})
    
    await _add_internal_notification(
        session=session,
        user_id=reservation.user_id,
        event="reservation_cancelled",
        title="Réservation annulée",
        message=(
            f"Votre réservation {reservation.reference} a été annulée."
        ),
        action_url="/pages/front-office/reservations",
    )

    await _commit(session)

    await session.refresh(reservation)

    _send_reservation_email(
        event="reservation.cancelled",
        sender=email_service.send_reservation_cancelled_email,
        reservation=reservation,
        name=_reservation_client_name(reservation),
        reservation_reference=reservation.reference,
        establishment_name=_reservation_establishment_name(reservation),
        cancellation_reason=reservation.cancellation_reason,
    )
    return reservation


async def update_reservation_status(
    reservation_id: UUID, data: Any, admin_user: User, session: AsyncSession,
    request: Request | None = None, reason: str | None = None,
) -> Reservation:
    reservation = await get_admin_reservation(reservation_id, session, for_update=True)
    new_status = getattr(data, "status", data)
    reason = reason or getattr(data, "reason", None)
    
    if new_status == reservation.status:
        return reservation
    
    allowed = ALLOWED_TRANSITIONS.get(reservation.status, set())
    
    if new_status not in allowed:
        raise _http_error(409, f"Transition interdite : {reservation.status} → {new_status}.")
    
    if new_status == ReservationStatus.CONFIRMEE:
        if reservation.payment_method is not None and _enum_value(reservation.payment_method) != "SUR_PLACE":
            if reservation.balance_due and money(reservation.balance_due) > ZERO:
                raise _http_error(409, "La réservation ne peut pas être confirmée tant que le paiement requis n'est pas enregistré.")
        
        reservation.verified_at = _now_utc().replace(tzinfo=None)
        reservation.verified_by = admin_user.id
        reservation.verification_result = "CONFIRMEE"
    
    if new_status == ReservationStatus.REFUSEE:
        reservation.refusal_reason = (reason or "").strip() or None
        if not reservation.refusal_reason:
            raise _http_error(422, "Le motif du refus est obligatoire.")
    
    if new_status == ReservationStatus.EN_COURS:
        reservation.started_at = _now_utc().replace(tzinfo=None)
    
    if new_status == ReservationStatus.TERMINEE:
        reservation.completed_at = _now_utc().replace(tzinfo=None)
    
    if new_status == ReservationStatus.ANNULEE:
        reservation.cancelled_at = _now_utc().replace(tzinfo=None)
        reservation.cancellation_reason = (reason or "").strip() or None
    
    reservation.status = new_status

        # Notifications internes selon la nouvelle transition.
    if new_status == ReservationStatus.CONFIRMEE:
        await _add_internal_notification(
            session=session,
            user_id=reservation.user_id,
            event="reservation_confirmed",
            title="Réservation confirmée",
            message=(
                f"Votre réservation {reservation.reference} est confirmée."
            ),
            action_url="/pages/front-office/reservations",
        )

    elif new_status == ReservationStatus.ANNULEE:
        await _add_internal_notification(
            session=session,
            user_id=reservation.user_id,
            event="reservation_cancelled",
            title="Réservation annulée",
            message=(
                f"Votre réservation {reservation.reference} a été annulée."
            ),
            action_url="/pages/front-office/reservations",
        )

    elif new_status == ReservationStatus.REFUSEE:
        await _add_internal_notification(
            session=session,
            user_id=reservation.user_id,
            event="reservation_refused",
            title="Réservation refusée",
            message=(
                f"Votre réservation {reservation.reference} a été refusée. "
                f"Motif : {reservation.refusal_reason}"
            ),
            action_url="/pages/front-office/reservations",
        )
    audit_reservation(session, admin_user, "reservation.status_changed", reservation, request, {"status": _enum_value(new_status), "reason": reason})
    await _commit(session)
    await session.refresh(reservation)

    if new_status == ReservationStatus.CONFIRMEE:
        _send_reservation_email(
            event="reservation.confirmed",
            sender=email_service.send_reservation_confirmed_email,
            reservation=reservation,
            name=_reservation_client_name(reservation),
            reservation_reference=reservation.reference,
            establishment_name=_reservation_establishment_name(reservation),
            start_date=reservation.start_date,
            end_date=reservation.end_date,
        )

    elif new_status == ReservationStatus.ANNULEE:
        _send_reservation_email(
            event="reservation.cancelled",
            sender=email_service.send_reservation_cancelled_email,
            reservation=reservation,
            name=_reservation_client_name(reservation),
            reservation_reference=reservation.reference,
            establishment_name=_reservation_establishment_name(reservation),
            cancellation_reason=reservation.cancellation_reason,
        )
    return reservation


async def record_reservation_refund(
    reservation_id: UUID, data: Any, admin_user: User, session: AsyncSession,
    request: Request | None = None,
) -> Reservation:
    reservation = await get_admin_reservation(reservation_id, session, for_update=True)
    confirmation = getattr(data, "confirmation", None)
    if confirmation != "REFUNDED":
        raise _http_error(422, "La confirmation explicite du remboursement est obligatoire.")
    if reservation.payment_status != PaymentStatus.PAYE:
        raise _http_error(409, "Seule une réservation payée peut être remboursée.")
    external_reference = (getattr(data, "external_reference", None) or "").strip()
    if not external_reference:
        raise _http_error(422, "La référence externe du remboursement est obligatoire.")
    reason = (getattr(data, "reason", None) or "").strip()
    if not reason:
        raise _http_error(422, "Le motif du remboursement est obligatoire.")
    amount_paid = money(reservation.amount_paid or reservation.total or ZERO)
    # L'enregistrement suppose que le remboursement a déjà été effectué auprès du prestataire.
    transaction_fields = _model_fields(Transaction)
    tx_values = {
        "reservation_id": reservation.id,
        "type": TransactionType.REFUND,
        "provider": getattr(reservation, "payment_provider", None) or "MANUAL",
        "status": PaymentStatus.REMBOURSE,
        "amount": amount_paid,
        "currency": reservation.currency,
        "external_reference": external_reference,
        "reference": external_reference,
        "description": reason,
    }
    session.add(Transaction(**{k: v for k, v in tx_values.items() if k in transaction_fields}))
    reservation.payment_status = PaymentStatus.REMBOURSE
    reservation.balance_due = ZERO
    
    audit_reservation(session, admin_user, "reservation.refund_recorded", reservation, request, {
        "amount": str(amount_paid), "external_reference": external_reference, "reason": reason,
    })
    
    await _add_internal_notification(
        session=session,
        user_id=reservation.user_id,
        event="refund",
        title="Remboursement enregistré",
        message=(
            f"Le remboursement de {amount_paid} {reservation.currency} "
            f"pour la réservation {reservation.reference} a été enregistré."
        ),
        action_url="/pages/front-office/reservations",
    )

    await _commit(session)

    await session.refresh(reservation)
    
    _send_reservation_email(
        event="reservation.refunded",
        sender=email_service.send_refund_email,
        reservation=reservation,
        name=_reservation_client_name(reservation),
        reservation_reference=reservation.reference,
        amount=amount_paid,
    )
    return reservation


# ---------------------------------------------------------------------------
# Statistiques admin
# ---------------------------------------------------------------------------

async def get_reservation_stats(
    session: AsyncSession, start_date: date | None = None, end_date: date | None = None,
) -> dict:
    stmt = select(Reservation)
    if start_date is not None:
        stmt = stmt.where(Reservation.start_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Reservation.start_date <= end_date)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    total = len(rows)
    count = lambda wanted: sum(1 for r in rows if r.status == wanted)
    paid = [r for r in rows if r.payment_status == PaymentStatus.PAYE]
    refunded = [r for r in rows if r.payment_status == PaymentStatus.REMBOURSE]
    pending_pay = [r for r in rows if r.payment_status == PaymentStatus.EN_ATTENTE]
    return {
        "total": total,
        "pending": count(ReservationStatus.EN_ATTENTE),
        "confirmed": count(ReservationStatus.CONFIRMEE),
        "ongoing": count(ReservationStatus.EN_COURS),
        "completed": count(ReservationStatus.TERMINEE),
        "cancelled": sum(1 for r in rows if r.status in {ReservationStatus.ANNULEE, ReservationStatus.REFUSEE, ReservationStatus.EXPIREE}),
        "payment_pending": len(pending_pay),
        "paid": len(paid),
        "refunded": len(refunded),
        "gross_paid": money(sum((money(r.amount_paid or r.total or ZERO) for r in paid), ZERO)),
        "gross_refunded": money(sum((money(r.amount_paid or r.total or ZERO) for r in refunded), ZERO)),
    }


# ---------------------------------------------------------------------------
# Point d'intégration paiement confirmé (à appeler depuis webhook vérifié)
# ---------------------------------------------------------------------------

async def mark_payment_succeeded(
    reservation_id: UUID,
    amount: Decimal,
    provider: str,
    provider_reference: str,
    session: AsyncSession,
    *,
    transaction_id: UUID | None = None,
) -> Reservation:
    """
    Enregistre un paiement uniquement après vérification cryptographique du webhook.
    Cette fonction ne valide pas elle-même une signature de prestataire.
    """
    reservation = await get_admin_reservation(reservation_id, session, for_update=True)
    amount = money(amount)
    
    if amount <= ZERO:
        raise _http_error(422, "Le montant du paiement doit être positif.")
    
    if amount > money(reservation.balance_due or ZERO):
        raise _http_error(409, "Le montant du paiement dépasse le solde restant.")
    
    if provider_reference:
        existing = await session.execute(
            select(Transaction.id).where(
                Transaction.provider == provider,
                or_(
                    getattr(Transaction, "external_reference", Transaction.id) == provider_reference,
                    getattr(Transaction, "reference", Transaction.id) == provider_reference,
                ),
            ).limit(1)
        )
        if existing.first():
            return reservation
    
    reservation.amount_paid = money((reservation.amount_paid or ZERO) + amount)
    reservation.balance_due = money(max(ZERO, money(reservation.total) - reservation.amount_paid))
    
    if reservation.balance_due == ZERO:
        reservation.payment_status = PaymentStatus.PAYE
        reservation.paid_at = _now_utc()
    else:
        reservation.payment_status = PaymentStatus.EN_ATTENTE
    
    reservation.payment_provider = provider
    reservation.payment_reference = provider_reference
    transaction_fields = _model_fields(Transaction)
    
    values = {
        "id": transaction_id,
        "reservation_id": reservation.id,
        "type": TransactionType.PAYMENT,
        "provider": provider,
        "status": PaymentStatus.PAYE,
        "amount": amount,
        "currency": reservation.currency,
        "external_reference": provider_reference,
        "reference": provider_reference,
        "paid_at": _now_utc(),
    }
    
    session.add(Transaction(**{k: v for k, v in values.items() if k in transaction_fields and v is not None}))
    
    await _add_internal_notification(
        session=session,
        user_id=reservation.user_id,
        event="payment_success",
        title="Paiement reçu",
        message=(
            f"Un paiement de {amount} {reservation.currency} "
            f"a été reçu pour la réservation {reservation.reference}."
        ),
        action_url="/pages/front-office/reservations",
    )
    
    await _commit(session)
    await session.refresh(reservation)

    _send_reservation_email(
        event="payment.succeeded",
        sender=email_service.send_payment_success_email,
        reservation=reservation,
        name=_reservation_client_name(reservation),
        reservation_reference=reservation.reference,
        amount=amount,
        transaction_reference=provider_reference,
    )

    return reservation


# ---------------------------------------------------------------------------
# Notifications centralisées BestRev
# ---------------------------------------------------------------------------

def _resolve_notification_type(event: str) -> NotificationType | None:
    """
    Résout le type à partir des membres réellement définis dans NotificationType.
    Évite d'introduire des valeurs d'enum inexistantes.
    """
    candidates = {
        "reservation_created": (
            "RESERVATION_CREATED", "RESERVATION", "BOOKING", "SYSTEM",
        ),
        "reservation_confirmed": (
            "RESERVATION_CONFIRMED", "RESERVATION", "BOOKING", "SYSTEM",
        ),
        "reservation_cancelled": (
            "RESERVATION_CANCELLED", "RESERVATION", "BOOKING", "SYSTEM",
        ),
        "reservation_refused": (
            "RESERVATION_REFUSED", "RESERVATION", "BOOKING", "SYSTEM",
        ),
        "payment_success": (
            "PAYMENT_SUCCESS", "PAYMENT", "TRANSACTION", "SYSTEM",
        ),
        "refund": (
            "REFUND", "PAYMENT", "TRANSACTION", "SYSTEM",
        ),
    }

    available = list(NotificationType)

    for candidate in candidates.get(event, ()):
        for member in available:
            if (
                member.name.upper() == candidate
                or str(member.value).upper() == candidate
            ):
                return member

    logger.warning(
        "Aucun NotificationType compatible avec l'événement %s. "
        "Valeurs disponibles : %s",
        event,
        [member.name for member in available],
    )
    return None


async def _add_internal_notification(
    *,
    session: AsyncSession,
    user_id: UUID | None,
    event: str,
    title: str,
    message: str,
    action_url: str | None = None,
) -> None:
    """
    Ajoute une notification dans la transaction métier.
    Le savepoint permet d'isoler un éventuel échec de cette insertion.
    """
    if user_id is None:
        return

    notification_type = _resolve_notification_type(event)

    if notification_type is None:
        return

    try:
        async with session.begin_nested():
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                title=title,
                message=message,
                action_url=action_url,
            )
            session.add(notification)
            await session.flush()

    except Exception:
        logger.exception(
            "Impossible de créer la notification interne : event=%s, user_id=%s",
            event,
            user_id,
        )


def _reservation_client_name(reservation: Reservation) -> str:
    first_name = getattr(reservation, "client_first_name", "") or ""
    last_name = getattr(reservation, "client_last_name", "") or ""

    return f"{first_name} {last_name}".strip() or "Client BestRev"


def _reservation_establishment_name(
    reservation: Reservation,
    establishment: Establishment | None = None,
) -> str:
    if establishment is not None:
        return getattr(establishment, "name", None) or "Établissement"

    snapshot = getattr(reservation, "pricing_snapshot", None) or {}

    if isinstance(snapshot, dict):
        return snapshot.get("establishment_name") or "Établissement"

    return "Établissement"


def _send_reservation_email(
    *,
    event: str,
    sender,
    reservation: Reservation,
    **kwargs,
) -> bool:
    """
    Envoie un email après le commit.
    Une erreur d'email ne doit jamais annuler l'opération métier.
    """
    recipient = getattr(reservation, "client_email", None)

    if not recipient:
        logger.warning(
            "Email non envoyé : adresse absente pour la réservation %s",
            getattr(reservation, "reference", None),
        )
        return False

    try:
        return dispatch_email(
            recipient=recipient,
            event_name=event,
            sender=sender,
            **kwargs,
        )
    except Exception:
        logger.exception(
            "Erreur lors de la notification email %s pour la réservation %s",
            event,
            getattr(reservation, "reference", None),
        )
        return False