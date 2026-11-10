from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.establishment import Establishment
from app.models.payment_condition import PaymentCondition
from app.models.establishment_payment_condition import (
    EstablishmentPaymentCondition,
)
from app.models.enums import PaymentConditionType
from app.schemas.payment_condition import (
    PaymentConditionCreate,
    PaymentConditionUpdate,
)


# =========================================================
# CONDITIONS DE PAIEMENT : CRUD
# =========================================================

def _validate_payment_condition(
    condition_type: PaymentConditionType | None,
    percentage: int | None,
) -> None:
    if condition_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Le type de condition de paiement est obligatoire.",
        )
    if (
        condition_type == PaymentConditionType.ACOMPTE
        and percentage is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Un pourcentage est obligatoire pour une condition d'acompte.",
        )
    if (
        condition_type != PaymentConditionType.ACOMPTE
        and percentage is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Le pourcentage ne s'applique qu'à une condition d'acompte.",
        )


async def create_payment_condition(
    data: PaymentConditionCreate,
    session: AsyncSession,
) -> PaymentCondition:
    _validate_payment_condition(data.condition_type, data.percentage)
    condition = PaymentCondition(**data.model_dump())

    session.add(condition)
    await session.commit()
    await session.refresh(condition)

    return condition


async def list_payment_conditions(
    session: AsyncSession,
) -> list[PaymentCondition]:

    result = await session.execute(
        select(PaymentCondition).order_by(PaymentCondition.name.asc())
    )

    return result.scalars().all()


async def get_payment_condition(
    condition_id: UUID,
    session: AsyncSession,
) -> PaymentCondition:

    result = await session.execute(
        select(PaymentCondition).where(
            PaymentCondition.id == condition_id
        )
    )

    condition = result.scalar_one_or_none()

    if condition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Condition de paiement introuvable.",
        )

    return condition


async def update_payment_condition(
    condition_id: UUID,
    data: PaymentConditionUpdate,
    session: AsyncSession,
) -> PaymentCondition:

    condition = await get_payment_condition(condition_id, session)

    changes = data.model_dump(exclude_unset=True)
    _validate_payment_condition(
        changes.get("condition_type", condition.condition_type),
        changes.get("percentage", condition.percentage),
    )

    for field, value in changes.items():
        setattr(condition, field, value)

    await session.commit()
    await session.refresh(condition)

    return condition


async def delete_payment_condition(
    condition_id: UUID,
    session: AsyncSession,
) -> dict:

    condition = await get_payment_condition(condition_id, session)

    # Empêcher la suppression d'une condition encore utilisée.
    result = await session.execute(
        select(EstablishmentPaymentCondition.establishment_id)
        .where(
            EstablishmentPaymentCondition.payment_condition_id
            == condition_id
        )
        .limit(1)
    )

    if result.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cette condition est associée à un ou plusieurs "
                "établissements. Retirez d'abord ces associations."
            ),
        )

    await session.delete(condition)
    await session.commit()

    return {"message": "Condition de paiement supprimée avec succès."}


# =========================================================
# CONDITIONS ASSOCIÉES À UN ÉTABLISSEMENT
# =========================================================

async def _get_establishment_for_payment_conditions(
    establishment_id: UUID,
    session: AsyncSession,
    *,
    owner_id: UUID | None = None,
    for_update: bool = False,
) -> Establishment:
    statement = select(Establishment).where(
        Establishment.id == establishment_id
    )
    if owner_id is not None:
        statement = statement.where(Establishment.owner_id == owner_id)
    if for_update:
        statement = statement.with_for_update()

    result = await session.execute(statement)
    establishment = result.scalars().first()
    if establishment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Établissement introuvable.",
        )
    return establishment


async def get_establishment_payment_conditions(
    establishment_id: UUID,
    session: AsyncSession,
    *,
    owner_id: UUID | None = None,
) -> list[PaymentCondition]:
    await _get_establishment_for_payment_conditions(
        establishment_id,
        session,
        owner_id=owner_id,
    )

    result = await session.execute(
        select(PaymentCondition)
        .join(
            EstablishmentPaymentCondition,
            EstablishmentPaymentCondition.payment_condition_id
            == PaymentCondition.id,
        )
        .where(
            EstablishmentPaymentCondition.establishment_id
            == establishment_id
        )
        .order_by(PaymentCondition.name.asc())
    )

    return result.scalars().all()


async def set_establishment_payment_conditions(
    establishment_id: UUID,
    payment_condition_ids: list[UUID],
    session: AsyncSession,
    *,
    owner_id: UUID | None = None,
) -> list[PaymentCondition]:
    await _get_establishment_for_payment_conditions(
        establishment_id,
        session,
        owner_id=owner_id,
        for_update=True,
    )

    # Éviter les doublons dans la liste reçue.
    unique_ids = list(dict.fromkeys(payment_condition_ids))

    # Vérifier que toutes les conditions existent.
    if unique_ids:
        result = await session.execute(
            select(PaymentCondition.id).where(
                PaymentCondition.id.in_(unique_ids)
            )
        )

        existing_ids = set(result.scalars().all())
        missing_ids = set(unique_ids) - existing_ids

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "Certaines conditions de paiement sont introuvables.",
                    "missing_ids": [str(item) for item in missing_ids],
                },
            )

    try:
        # Supprimer les anciennes associations.
        await session.execute(
            delete(EstablishmentPaymentCondition).where(
                EstablishmentPaymentCondition.establishment_id
                == establishment_id
            )
        )

        # Ajouter les nouvelles associations.
        links = [
            EstablishmentPaymentCondition(
                establishment_id=establishment_id,
                payment_condition_id=condition_id,
            )
            for condition_id in unique_ids
        ]

        session.add_all(links)

        await session.commit()

    except Exception:
        await session.rollback()
        raise

    return await get_establishment_payment_conditions(
        establishment_id,
        session,
        owner_id=owner_id,
    )