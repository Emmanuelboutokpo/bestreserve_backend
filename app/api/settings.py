import json
import re
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.cores.db import get_session
from app.cores.redis import token_blacklist
from app.dependencies.dependencies import require_admin
from app.models import ActivityLog, PlatformSetting, User
from app.schemas.settings import (
    AdminSettingsUpdate,
    MaintenanceRequest,
    ServiceStatusPublic,
    SettingPublic,
)


admin_settings_router = APIRouter(
    prefix="/admin/settings",
    tags=["Paramètres plateforme"],
    dependencies=[Depends(require_admin)],
)

WRITABLE_SETTINGS = {
    "site_name",
    "support_email",
    "default_currency",
    "default_language",
    "service_fee_percent",
    "booking_advance_days",
    "booking_min_notice_hours",
    "cancellation_free_hours",
}
MAINTENANCE_SETTING_KEYS = {"maintenance_mode", "maintenance_message"}
SENSITIVE_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "private_key",
    "webhook_secret",
    "credential",
)


def _sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_PARTS)


def _value_json(setting: PlatformSetting):
    if setting.value_json is not None:
        return setting.value_json
    if setting.value is None:
        return None
    try:
        return json.loads(setting.value)
    except (TypeError, json.JSONDecodeError):
        return setting.value


def _setting_public(setting: PlatformSetting) -> dict:
    return {
        "key": setting.key,
        "value": setting.value,
        "value_json": _value_json(setting),
        "description": setting.description,
        "section": setting.section,
        "is_public": setting.is_public,
        "updated_at": setting.updated_at,
    }


def _validate_setting(key: str, value):
    if key not in WRITABLE_SETTINGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Le paramètre '{key}' n'est pas modifiable via cette API.",
        )
    if key == "site_name":
        if not isinstance(value, str) or not 2 <= len(value.strip()) <= 150:
            raise HTTPException(status_code=422, detail="Nom du site invalide.")
        return value.strip()
    if key == "support_email":
        try:
            return str(TypeAdapter(EmailStr).validate_python(value))
        except (ValidationError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Email de support invalide.") from exc
    if key == "default_currency":
        if (
            not isinstance(value, str)
            or len(value.strip()) != 3
            or not value.strip().isascii()
            or not value.strip().isalpha()
        ):
            raise HTTPException(status_code=422, detail="Code devise invalide.")
        return value.strip().upper()
    if key == "default_language":
        if not isinstance(value, str) or not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", value):
            raise HTTPException(status_code=422, detail="Code langue invalide.")
        return value
    if key == "service_fee_percent":
        if isinstance(value, bool):
            raise HTTPException(status_code=422, detail="Pourcentage de frais invalide.")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Pourcentage de frais invalide.") from exc
        if not decimal_value.is_finite() or decimal_value < 0 or decimal_value > 30:
            raise HTTPException(status_code=422, detail="Les frais doivent être compris entre 0 et 30%.")
        return str(decimal_value.normalize())
    bounds = {
        "booking_advance_days": (1, 3650),
        "booking_min_notice_hours": (0, 720),
        "cancellation_free_hours": (0, 720),
    }
    if key in bounds:
        low, high = bounds[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise HTTPException(status_code=422, detail=f"Valeur invalide pour '{key}'.")
        return value
    raise HTTPException(status_code=422, detail="Valeur de paramètre invalide.")


def _audit_setting(
    session: AsyncSession,
    actor: User,
    request: Request,
    keys: list[str],
) -> None:
    session.add(
        ActivityLog(
            user_id=actor.id,
            action="ADMIN_SETTINGS_UPDATED",
            entity_type="platform_setting",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:1000] or None,
            metadata_json={"keys": sorted(keys)},
        )
    )


@admin_settings_router.get("", response_model=list[SettingPublic])
async def list_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(PlatformSetting)
        .where(PlatformSetting.key.in_(WRITABLE_SETTINGS | MAINTENANCE_SETTING_KEYS))
        .order_by(PlatformSetting.section, PlatformSetting.key)
    )
    return [
        _setting_public(setting)
        for setting in result.scalars().all()
        if not _sensitive_key(setting.key)
    ]


@admin_settings_router.get("/services/status", response_model=ServiceStatusPublic)
async def get_services_status(
    session: AsyncSession = Depends(get_session),
):
    try:
        await session.execute(select(1))
        database_status = "available"
    except Exception:
        database_status = "unavailable"
    try:
        await token_blacklist.ping()
        redis_status = "available"
    except Exception:
        redis_status = "unavailable"
    cloudinary_status = (
        "configured"
        if settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
        else "not_configured"
    )
    fedapay_status = "configured" if settings.fedapay_api_key else "not_configured"
    webpush_status = (
        "configured"
        if settings.push_encryption_key
        and settings.webpush_vapid_public_key
        and settings.webpush_vapid_private_key
        and settings.webpush_vapid_subject
        else "not_configured"
    )
    return {
        "database": database_status,
        "redis": redis_status,
        "cloudinary": cloudinary_status,
        "fedapay": fedapay_status,
        "webpush": webpush_status,
        "fedapay_environment": settings.fedapay_environment,
    }


@admin_settings_router.get("/{key}", response_model=SettingPublic)
async def get_setting(key: str, session: AsyncSession = Depends(get_session)):
    if key not in WRITABLE_SETTINGS | MAINTENANCE_SETTING_KEYS or _sensitive_key(key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paramètre introuvable.",
        )
    result = await session.execute(
        select(PlatformSetting).where(PlatformSetting.key == key)
    )
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paramètre introuvable.",
        )
    return _setting_public(setting)


@admin_settings_router.put("")
async def update_settings(
    data: AdminSettingsUpdate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    changes = {
        key: _validate_setting(key, value)
        for key, value in data.settings.items()
    }
    result = await session.execute(
        select(PlatformSetting)
        .where(PlatformSetting.key.in_(changes))
        .with_for_update()
    )
    existing = {setting.key: setting for setting in result.scalars().all()}
    for key, value in changes.items():
        setting = existing.get(key)
        if setting is None:
            setting = PlatformSetting(
                key=key,
                section="general",
                is_public=False,
            )
            session.add(setting)
        if isinstance(value, dict):
            setting.value = None
            setting.value_json = value
        else:
            setting.value = json.dumps(value, ensure_ascii=False)
            setting.value_json = None
        setting.updated_by = actor.id
    _audit_setting(session, actor, request, list(changes))
    await session.commit()
    return {"updated": sorted(changes)}


@admin_settings_router.post("/maintenance")
async def set_maintenance_mode(
    data: MaintenanceRequest,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PlatformSetting)
        .where(
            PlatformSetting.key.in_(MAINTENANCE_SETTING_KEYS)
        )
        .with_for_update()
    )
    saved = {setting.key: setting for setting in result.scalars().all()}
    enabled_setting = saved.get("maintenance_mode")
    if enabled_setting is None:
        enabled_setting = PlatformSetting(
            key="maintenance_mode",
            section="system",
            is_public=False,
        )
        session.add(enabled_setting)
    enabled_setting.value = json.dumps(data.enabled)
    enabled_setting.updated_by = actor.id

    message_setting = saved.get("maintenance_message")
    if message_setting is None:
        message_setting = PlatformSetting(
            key="maintenance_message",
            section="system",
            is_public=False,
        )
        session.add(message_setting)
    message_setting.value = json.dumps(data.message, ensure_ascii=False)
    message_setting.updated_by = actor.id
    _audit_setting(
        session,
        actor,
        request,
        ["maintenance_mode", "maintenance_message"],
    )

    try:
        previous_maintenance_state = await token_blacklist.get(
            "settings:maintenance:enabled"
        )
        await token_blacklist.set(
            "settings:maintenance:enabled",
            "1" if data.enabled else "0",
        )
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis est indisponible; le mode maintenance n'a pas été modifié.",
        ) from exc

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        try:
            if previous_maintenance_state is None:
                await token_blacklist.delete("settings:maintenance:enabled")
            else:
                await token_blacklist.set(
                    "settings:maintenance:enabled",
                    previous_maintenance_state,
                )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible d'enregistrer le mode maintenance.",
        ) from exc
    return {
        "maintenance_enabled": data.enabled,
        "message": data.message,
    }