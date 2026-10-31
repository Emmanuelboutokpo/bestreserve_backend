from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin

from app.schemas.payment_condition import (
    PaymentConditionCreate,
    PaymentConditionUpdate,
    PaymentConditionPublic,
    EstablishmentPaymentConditionsUpdate,
)

from app.services import payment_condition as payment_condition_service


admin_payment_conditions_router = APIRouter(
    prefix="/admin",
    tags=["Administration - Conditions de paiement"],
    dependencies=[Depends(require_admin)],
)


# =========================================================
# CRUD DES CONDITIONS
# =========================================================

@admin_payment_conditions_router.post(
    "/payment-conditions",
    response_model=PaymentConditionPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une condition de paiement",
)
async def create_payment_condition(
    data: PaymentConditionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.create_payment_condition(
        data,
        session,
    )


@admin_payment_conditions_router.get(
    "/payment-conditions",
    response_model=list[PaymentConditionPublic],
    summary="Lister les conditions de paiement",
)
async def list_payment_conditions(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.list_payment_conditions(
        session,
    )


@admin_payment_conditions_router.get(
    "/payment-conditions/{condition_id}",
    response_model=PaymentConditionPublic,
    summary="Consulter une condition de paiement",
)
async def get_payment_condition(
    condition_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.get_payment_condition(
        condition_id,
        session,
    )


@admin_payment_conditions_router.patch(
    "/payment-conditions/{condition_id}",
    response_model=PaymentConditionPublic,
    summary="Modifier une condition de paiement",
)
async def update_payment_condition(
    condition_id: UUID,
    data: PaymentConditionUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.update_payment_condition(
        condition_id,
        data,
        session,
    )


@admin_payment_conditions_router.delete(
    "/payment-conditions/{condition_id}",
    summary="Supprimer une condition de paiement",
)
async def delete_payment_condition(
    condition_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.delete_payment_condition(
        condition_id,
        session,
    )


# =========================================================
# ASSOCIATION AUX ÉTABLISSEMENTS
# =========================================================

@admin_payment_conditions_router.put(
    "/establishments/{establishment_id}/payment-conditions",
    response_model=list[PaymentConditionPublic],
    summary="Remplacer les conditions d'un établissement",
)
async def set_establishment_payment_conditions(
    establishment_id: UUID,
    data: EstablishmentPaymentConditionsUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.set_establishment_payment_conditions(
        establishment_id,
        data.payment_condition_ids,
        session,
    )


@admin_payment_conditions_router.get(
    "/establishments/{establishment_id}/payment-conditions",
    response_model=list[PaymentConditionPublic],
    summary="Consulter les conditions d'un établissement",
)
async def get_establishment_payment_conditions(
    establishment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.get_establishment_payment_conditions(
        establishment_id,
        session,
    )