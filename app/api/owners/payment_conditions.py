from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import User
from app.schemas.payment_condition import (
    EstablishmentPaymentConditionsUpdate,
    PaymentConditionPublic,
)
from app.services import payment_condition as payment_condition_service


owner_payment_conditions_router = APIRouter(
    prefix="/owners",
    tags=["Propriétaire - Conditions de paiement"],
    dependencies=[Depends(require_proprietaire)],
)


@owner_payment_conditions_router.get(
    "/payment-conditions",
    response_model=list[PaymentConditionPublic],
    summary="Lister les conditions de paiement disponibles",
)
async def list_payment_conditions(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.list_payment_conditions(session)


@owner_payment_conditions_router.get(
    "/payment-conditions/{condition_id}",
    response_model=PaymentConditionPublic,
    summary="Consulter une condition de paiement disponible",
)
async def get_payment_condition(
    condition_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.get_payment_condition(
        condition_id,
        session,
    )


@owner_payment_conditions_router.get(
    "/establishments/{establishment_id}/payment-conditions",
    response_model=list[PaymentConditionPublic],
    summary="Lister les conditions de paiement d'un établissement",
)
async def get_establishment_payment_conditions(
    establishment_id: UUID,
    owner: Annotated[User, Depends(require_proprietaire)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.get_establishment_payment_conditions(
        establishment_id,
        session,
        owner_id=owner.id,
    )


@owner_payment_conditions_router.put(
    "/establishments/{establishment_id}/payment-conditions",
    response_model=list[PaymentConditionPublic],
    summary="Choisir les conditions de paiement d'un établissement",
)
async def set_establishment_payment_conditions(
    establishment_id: UUID,
    data: EstablishmentPaymentConditionsUpdate,
    owner: Annotated[User, Depends(require_proprietaire)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.set_establishment_payment_conditions(
        establishment_id,
        data.payment_condition_ids,
        session,
        owner_id=owner.id,
    )
