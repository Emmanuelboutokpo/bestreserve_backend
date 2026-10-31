from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentConditionType


class PaymentConditionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=150)
    condition_type: PaymentConditionType
    percentage: int | None = Field(default=None, ge=1, le=100)


class PaymentConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=150)
    condition_type: PaymentConditionType | None = None
    percentage: int | None = Field(default=None, ge=1, le=100)


class PaymentConditionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    condition_type: PaymentConditionType
    percentage: int | None = None


class EstablishmentPaymentConditionsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_condition_ids: list[UUID] = Field(default_factory=list)