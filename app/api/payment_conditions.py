from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session

from app.schemas.payment_condition import PaymentConditionPublic

from app.services import payment_condition as payment_condition_service


payment_conditions_router = APIRouter(
    prefix="/establishments",
    tags=["Conditions de paiement"],
)


@payment_conditions_router.get(
    "/{establishment_id}/payment-conditions",
    response_model=list[PaymentConditionPublic],
    summary="Consulter les conditions de paiement d'un établissement",
)
async def get_public_establishment_payment_conditions(
    establishment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await payment_condition_service.get_establishment_payment_conditions(
        establishment_id,
        session,
    )