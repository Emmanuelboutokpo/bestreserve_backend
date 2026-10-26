from datetime import datetime
import re
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.enums import NotificationType


class PushSubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=16, max_length=256)
    auth: str = Field(min_length=8, max_length=128)

    @field_validator("p256dh", "auth")
    @classmethod
    def validate_base64url(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Clé push invalide.")
        return value


class PushSubscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: AnyHttpUrl
    keys: PushSubscriptionKeys
    expiration_time: int | None = Field(default=None, ge=0)

    @field_validator("endpoint")
    @classmethod
    def require_https_endpoint(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("L'endpoint push doit utiliser HTTPS.")
        host = (value.host or "").lower().rstrip(".")
        allowed_host = (
            host == "fcm.googleapis.com"
            or host.endswith(".fcm.googleapis.com")
            or host == "push.services.mozilla.com"
            or host.endswith(".push.services.mozilla.com")
            or host == "web.push.apple.com"
            or host.endswith(".notify.windows.com")
        )
        if not allowed_host:
            raise ValueError("Fournisseur push non pris en charge.")
        return value


class VapidPublicKeyResponse(BaseModel):
    public_key: str


class AdminNotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    type: NotificationType
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=2000)
    action_url: str | None = Field(default=None, max_length=1000)

    @field_validator("title", "message")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le texte ne peut pas être vide.")
        return value

    @field_validator("action_url")
    @classmethod
    def require_internal_action(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value.startswith("/") or value.startswith("//") or "\\" in value:
            raise ValueError("L'action doit être une URL relative interne.")
        return value


class AdminNotificationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: NotificationType
    title: str
    message: str
    action_url: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class AdminNotificationPage(BaseModel):
    items: list[AdminNotificationPublic]
    total: int
    limit: int
    offset: int