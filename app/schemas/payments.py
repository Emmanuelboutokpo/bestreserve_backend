from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import PaymentMethod, PaymentStatus


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    payment_method: PaymentMethod


class CheckoutResponse(BaseModel):
    transaction_ref: str
    public_key: str
    partner_id: str
    amount: int
    currency: str
    status: PaymentStatus
    sandbox: bool
    provider_transaction_id: str | None = None
    requires_widget: bool


class PaymentConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_ref: str = Field(min_length=8, max_length=40)

    provider_transaction_id: str = Field(
        min_length=1,
        max_length=255,
    )

class PaymentPublic(BaseModel):
    transaction_ref: str
    reservation_reference: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    provider: str | None
    created_at: datetime
    updated_at: datetime


class PaymentRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_reference: str = Field(min_length=3, max_length=255)
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason", "external_reference")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Le motif doit contenir au moins trois caractères.")
        return value


class AdminPaymentPublic(PaymentPublic):
    id: UUID
    user_id: UUID
    reservation_id: UUID
    provider_transaction_id: str | None


class FedaPayCheckoutPayload(BaseModel):
    amount: int = Field(gt=0)
    currency: Literal["XOF"]
    description: str = Field(max_length=255)
    callback_url: str = Field(max_length=1000)
    merchant_reference: str = Field(max_length=40)
    custom_metadata: dict[str, str]
    customer: dict