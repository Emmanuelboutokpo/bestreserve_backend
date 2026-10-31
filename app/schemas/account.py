import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import NotificationType


class AccountProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    firstName: str | None = Field(default=None, max_length=100)
    lastName: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, min_length=2, max_length=5)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("firstName", "lastName", "city")
    @classmethod
    def normalize_non_empty_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("La valeur ne peut pas être vide.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not re.fullmatch(r"\+?[0-9(). -]{6,30}", value):
            raise ValueError("Numéro de téléphone invalide.")
        return value

  
    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?", value):
            raise ValueError("Code de langue invalide.")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Code devise invalide.")
        return value

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Aucune information à modifier.")
        return self


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if (
            not any(char.isupper() for char in value)
            or not any(char.islower() for char in value)
            or not any(char.isdigit() for char in value)
            or not any(not char.isalnum() for char in value)
        ):
            raise ValueError(
                "Le nouveau mot de passe doit contenir une majuscule, "
                "une minuscule, un chiffre et un caractère spécial."
            )
        return value

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Les mots de passe ne correspondent pas.")
        if self.new_password == self.current_password:
            raise ValueError("Le nouveau mot de passe doit être différent.")
        return self


class AccountDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: Literal["DELETE"]
    current_password: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def require_single_reauthentication(self):
        if not bool(self.current_password):
            raise ValueError(
                "Fournissez soit le mot de passe actuel !"
            )
        return self


class ConsentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketing_email: bool | None = None
    marketing_sms: bool | None = None
    analytics: bool | None = None
    personalization: bool | None = None

    @model_validator(mode="after")
    def validate_consents(self):
        if not self.model_fields_set:
            raise ValueError("Aucun consentement à modifier.")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Chaque consentement fourni doit être vrai ou faux.")
        return self


class NotificationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    title: str
    message: str
    action_url: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationPublic]
    limit: int
    offset: int


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)