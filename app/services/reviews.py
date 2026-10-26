# app/services/review.py

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import Establishment, Reservation, Review, User
from app.models.enums import ReservationStatus
from app.schemas.establishment import ReviewPublic
from app.schemas.reviews import (
    ReviewAdminPublic,
    ReviewCreate,
    ReviewPage,
    ReviewUpdate,
)

from sqlalchemy.orm import selectinload


# ============================================================
# CONSTANTES
# ============================================================

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _http_error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _review_query():
    return select(Review).options(
        selectinload(Review.user).selectinload(User.profile)
    )


async def _get_review(
    review_id: UUID,
    session: AsyncSession,
    *,
    for_update: bool = False,
) -> Review:
    query = _review_query().where(Review.id == review_id)

    if for_update:
        query = query.with_for_update()

    result = await session.execute(query)
    review = result.scalars().first()

    if review is None:
        raise _http_error(
            status.HTTP_404_NOT_FOUND,
            "Avis introuvable.",
        )

    return review


def _author_name(user: User | None) -> str:
    if user is None:
        return "Client"

    profile = getattr(user, "profile", None)

    if profile is None:
        return "Client"

    first_name = (
        getattr(profile, "first_name", None)
        or getattr(profile, "firstname", None)
        or ""
    )

    last_name = (
        getattr(profile, "last_name", None)
        or getattr(profile, "lastname", None)
        or ""
    )

    full_name = f"{first_name} {last_name}".strip()

    return full_name or "Client"


def _serialize_public_review(
    review: Review,
    *,
    user: User | None = None,
) -> dict:
    author = user if user is not None else getattr(review, "user", None)

    return {
        "id": review.id,
        "author_name": _author_name(author),
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at,
    }

# ============================================================
# CONSULTATION PUBLIQUE
# ============================================================

async def list_establishment_reviews(
    establishment_id: UUID,
    limit: int,
    offset: int,
    session: AsyncSession,
) -> list[ReviewPublic]:

    # Vérifier que l'établissement existe.
    establishment_result = await session.execute(
        select(Establishment.id).where(
            Establishment.id == establishment_id
        )
    )

    if establishment_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Établissement introuvable.",
        )

    # Récupérer uniquement les avis approuvés.
    query = (
        _review_query()
        .where(
            Review.establishment_id == establishment_id,
            Review.is_approved.is_(True),
        )
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(query)
    reviews = result.scalars().all()

    return [
        ReviewPublic.model_validate(
            _serialize_public_review(review)
        )
        for review in reviews
    ]

# ============================================================
# CRÉATION D'UN AVIS
# ============================================================

async def create_review(
    establishment_id: UUID,
    data: ReviewCreate,
    current_user: User,
    session: AsyncSession,
) -> Review:
    
 
    reservation_result = await session.execute(
        select(Reservation)
        .where(
            Reservation.id == data.reservation_id,
            Reservation.user_id == current_user.id,
            Reservation.establishment_id == establishment_id,
        )
        .with_for_update()
    )

    reservation = reservation_result.scalars().first()

    if reservation is None:
        raise _http_error(
            status.HTTP_404_NOT_FOUND,
            "Réservation introuvable pour ce client et cet établissement.",
        )

    if reservation.status != ReservationStatus.TERMINEE:
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "Vous pouvez laisser un avis uniquement après "
            "la fin de la réservation.",
        )

    existing_result = await session.execute(
        select(Review.id).where(
            Review.reservation_id == reservation.id
        )
    )

    if existing_result.scalar_one_or_none() is not None:
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "Un avis existe déjà pour cette réservation.",
        )

    review = Review(
        establishment_id=establishment_id,
        user_id=current_user.id,
        reservation_id=reservation.id,
        rating=data.rating,
        comment=data.comment,
        is_approved=False,
    )

    try:
        session.add(review)
        await session.commit()
        await session.refresh(review)

    except IntegrityError as exc:
        await session.rollback()

        # La contrainte unique en base protège aussi contre
        # les créations concurrentes.
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "Un avis existe déjà pour cette réservation.",
        ) from exc

    return ReviewPublic.model_validate(
    _serialize_public_review(review, user=current_user)
    )


# ============================================================
# MODIFICATION D'UN AVIS
# ============================================================

async def update_review(
    review_id: UUID,
    data: ReviewUpdate,
    current_user: User,
    session: AsyncSession,
) -> Review:
    """
    Un client ne peut modifier que son propre avis.
    """

    payload = data.model_dump(exclude_unset=True)

    unsupported_fields = {
        "cleanliness_rating",
        "service_rating",
        "location_rating",
        "value_rating",
    }

    provided_unsupported_fields = (
        unsupported_fields.intersection(payload.keys())
    )

    if provided_unsupported_fields:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Les notes secondaires ne sont pas encore prises "
            "en charge par le modèle Review.",
        )

    review = await _get_review(
        review_id,
        session,
        for_update=True,
    )

    if review.user_id != current_user.id:
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "Vous ne pouvez modifier que vos propres avis.",
        )

    for field in ("rating", "comment"):
        if field in payload:
            setattr(review, field, payload[field])

    # Une modification repasse l'avis en modération.
    review.is_approved = False

    if hasattr(review, "approved_at"):
        review.approved_at = None

    try:
        await session.commit()
        await session.refresh(review)

    except Exception:
        await session.rollback()
        raise

    return ReviewPublic.model_validate(
    _serialize_public_review(review, user=current_user)
)


# ============================================================
# SUPPRESSION PAR LE CLIENT
# ============================================================

async def delete_review(
    review_id: UUID,
    current_user: User,
    session: AsyncSession,
) -> None:

    review = await _get_review(
        review_id,
        session,
        for_update=True,
    )

    if review.user_id != current_user.id:
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "Vous ne pouvez supprimer que vos propres avis.",
        )

  
    await session.delete(review)

    await session.commit()


# ============================================================
# LISTE ADMINISTRATIVE
# ============================================================
async def list_admin_reviews(
    limit: int,
    offset: int,
    approved: bool | None,
    establishment_id: UUID | None,
    session: AsyncSession,
) -> ReviewPage:
    """Liste les avis pour l'administration avec pagination."""

    query = _review_query()

    if approved is not None:
        query = query.where(
            Review.is_approved.is_(approved)
        )

    if establishment_id is not None:
        query = query.where(
            Review.establishment_id == establishment_id
        )

    # Compter les avis correspondant aux filtres.
    count_query = (
        select(func.count())
        .select_from(Review)
    )

    if approved is not None:
        count_query = count_query.where(
            Review.is_approved.is_(approved)
        )

    if establishment_id is not None:
        count_query = count_query.where(
            Review.establishment_id == establishment_id
        )

    total = await session.scalar(count_query)

    # Récupérer les avis paginés.
    result = await session.execute(
        query
        .order_by(
            Review.created_at.desc(),
            Review.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    reviews = result.scalars().all()

    # Convertir les objets SQLAlchemy en schémas Pydantic.
    items = [
    ReviewAdminPublic.model_validate(
        {
            **_serialize_public_review(review),
            "user_id": review.user_id,
            "reservation_id": review.reservation_id,
            "establishment_id": review.establishment_id,
            "is_approved": review.is_approved,
        }
    )
    for review in reviews
]
    return ReviewPage(
        items=items,
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )

# ============================================================
# APPROBATION ADMINISTRATIVE
# ============================================================


async def approve_review(
    *,
    review_id: UUID,
    session: AsyncSession,
) -> ReviewAdminPublic:
    result = await session.execute(
        select(Review)
        .options(
            selectinload(Review.user).selectinload(User.profile)
        )
        .where(Review.id == review_id)
    )

    review = result.scalar_one_or_none()

    if review is None:
        raise HTTPException(
            status_code=404,
            detail="Avis introuvable.",
        )

    review.is_approved = True
    review.approved_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(review)

    data = {
    **_serialize_public_review(review),
    "user_id": review.user_id,
    "reservation_id": review.reservation_id,
    "establishment_id": review.establishment_id,
    "is_approved": review.is_approved,
    "approved_at": review.approved_at,
}


    return ReviewAdminPublic.model_validate(data)


# ============================================================
# SUPPRESSION ADMINISTRATIVE
# ============================================================

async def delete_admin_review(
    review_id: UUID,
    session: AsyncSession,
) -> None:

    review = await _get_review(
        review_id,
        session,
        for_update=True,
    )

    await session.delete(review)

    await session.commit()