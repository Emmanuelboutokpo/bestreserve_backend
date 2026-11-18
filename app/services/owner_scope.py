import unicodedata
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Establishment, Reservation, User
from app.models.enums import UserRole


_OWNER_LODGING_CATEGORY_NAMES = frozenset(
    {
        "hebergement",
        "hebergements",
        "hotel",
        "hotels",
        "logement",
        "logements",
        "accommodation",
        "accommodations",
        "lodging",
        "lodgings",
    }
)

_OWNER_LODGING_CATEGORY_SQL_NAMES = frozenset(
    {
        *_OWNER_LODGING_CATEGORY_NAMES,
        "hébergement",
        "hébergements",
        "hôtel",
        "hôtels",
    }
)

_ADMIN_MANAGED_CATEGORY_PATTERNS = {
    "restaurant": (
        "%restaurant%",
        "%restauration%",
        "%food%",
    ),
    "loisir": (
        "%loisir%",
        "%activit%",
        "%leisure%",
        "%activity%",
        "%experience%",
        "%expérience%",
    ),
}


def category_type_for_name(name: str) -> str | None:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = normalized.strip().casefold()

    if normalized in _OWNER_LODGING_CATEGORY_NAMES:
        return "hebergement"
    if any(
        keyword in normalized
        for keyword in ("restaurant", "restauration", "food")
    ):
        return "restaurant"
    if any(
        keyword in normalized
        for keyword in ("loisir", "activite", "leisure", "activity", "experience")
    ):
        return "loisir"
    return None


def is_owner_managed_category_name(name: str) -> bool:
    return category_type_for_name(name) == "hebergement"


def admin_managed_establishment_ids(category_type: str | None = None):
    category_types = (
        (category_type,)
        if category_type not in (None, "all")
        else tuple(_ADMIN_MANAGED_CATEGORY_PATTERNS)
    )
    patterns = (
        pattern
        for kind in category_types
        for pattern in _ADMIN_MANAGED_CATEGORY_PATTERNS[kind]
    )
    category_filter = func.lower(func.trim(Category.name)).like

    return (
        select(Establishment.id)
        .join(Category, Category.id == Establishment.category_id)
        .where(or_(*(category_filter(pattern) for pattern in patterns)))
    )


async def validate_owner_category(
    category_id: UUID,
    session: AsyncSession,
) -> None:
    result = await session.execute(
        select(Category.name).where(Category.id == category_id)
    )
    category_name = result.scalar_one_or_none()

    if category_name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Catégorie introuvable.",
        )
    if not is_owner_managed_category_name(category_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Les propriétaires peuvent gérer uniquement "
                "les établissements d'hébergement."
            ),
        )


async def validate_admin_managed_category(
    category_id: UUID,
    session: AsyncSession,
) -> str:
    result = await session.execute(
        select(Category.name).where(Category.id == category_id)
    )
    category_name = result.scalar_one_or_none()

    if category_name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Catégorie introuvable.",
        )

    category_type = category_type_for_name(category_name)
    if category_type not in _ADMIN_MANAGED_CATEGORY_PATTERNS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Cette route gère uniquement les restaurants "
                "et les lieux de loisirs."
            ),
        )
    return category_type


def owner_establishment_ids(owner_id: UUID):
    return (
        select(Establishment.id)
        .join(Category, Category.id == Establishment.category_id)
        .where(
            Establishment.owner_id == owner_id,
            func.lower(func.trim(Category.name)).in_(
                _OWNER_LODGING_CATEGORY_SQL_NAMES
            ),
        )
    )


def owner_customer_ids(owner_id: UUID):
    reservation_customer_ids = (
        select(Reservation.user_id)
        .join(
            Establishment,
            Establishment.id == Reservation.establishment_id,
        )
        .where(
            Establishment.id.in_(owner_establishment_ids(owner_id))
        )
    )
    return select(User.id).where(
        User.role == UserRole.CLIENT,
        or_(
            User.created_by == owner_id,
            User.id.in_(reservation_customer_ids),
        ),
    )
