from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SettingValue = str | bool | int | float | dict[str, Any] | None


class AdminSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: dict[str, SettingValue] = Field(min_length=1, max_length=50)

    @field_validator("settings")
    @classmethod
    def validate_setting_keys(cls, value: dict[str, SettingValue]):
        for key in value:
            if not key or len(key) > 150 or not key.replace("_", "").isalnum():
                raise ValueError("Clé de paramètre invalide.")
        return value


class MaintenanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    message: str | None = Field(default=None, max_length=500)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SettingPublic(BaseModel):
    key: str
    value: str | None
    value_json: Any | None
    description: str | None
    section: str | None
    is_public: bool
    updated_at: datetime


class ServiceStatusPublic(BaseModel):
    database: str
    redis: str
    cloudinary: str
    fedapay: str
    webpush: str
    fedapay_environment: str