# app/services/notification.py


from fastapi import HTTPException, status
import logging
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.notification import Notification
from app.models.enums import NotificationType
from app.models import User

from datetime import datetime, timezone
from typing import Any
from uuid import UUID



logger = logging.getLogger(__name__)


async def create_notification(
    *,
    session: AsyncSession,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    action_url: str | None = None,
) -> Notification:
    """
    Prépare une notification interne.

    Ne commit pas : l'appelant contrôle la transaction.
    """

    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title.strip(),
        message=message.strip(),
        action_url=action_url,
    )

    session.add(notification)
    await session.flush()

    return notification


async def list_user_notifications(
    *,
    session: AsyncSession,
    user_id: UUID,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Retourne uniquement les notifications de l'utilisateur concerné."""

    filters = [Notification.user_id == user_id]

    if unread_only:
        filters.append(Notification.is_read.is_(False))

    count_result = await session.execute(
        select(func.count(Notification.id)).where(*filters)
    )

    result = await session.execute(
        select(Notification)
        .where(*filters)
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return {
        "items": result.scalars().all(),
        "total": count_result.scalar_one(),
        "limit": limit,
        "offset": offset,
    }


async def mark_notification_as_read(
    *,
    session: AsyncSession,
    user_id: UUID,
    notification_id: UUID,
) -> Notification | None:
    """Marque comme lue une notification appartenant à l'utilisateur."""

    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )

    notification = result.scalar_one_or_none()

    if notification is None:
        return None

    if not notification.is_read:
        notification.mark_as_read()
        session.add(notification)
        await session.flush()

    return notification


async def mark_all_notifications_as_read(
    *,
    session: AsyncSession,
    user_id: UUID,
) -> int:
    """Marque comme lues toutes les notifications de l'utilisateur."""

    result = await session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )

    notifications = result.scalars().all()

    for notification in notifications:
        notification.mark_as_read()
        session.add(notification)

    await session.flush()

    return len(notifications)



def _notification_to_dict(
    notification: Notification,
) -> dict[str, Any]:
    """Sérialise une notification pour l'API."""

    notification_type = notification.type

    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "type": (
            notification_type.value
            if hasattr(notification_type, "value")
            else notification_type
        ),
        "title": notification.title,
        "message": notification.message,
        "action_url": notification.action_url,
        "is_read": notification.is_read,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
    }


async def _get_notification(
    *,
    notification_id: UUID,
    session: AsyncSession,
    user_id: UUID | None = None,
    for_update: bool = False,
) -> Notification:
    """Récupère une notification, avec verrouillage facultatif."""

    statement = select(Notification).where(
        Notification.id == notification_id,
    )

    if user_id is not None:
        statement = statement.where(Notification.user_id == user_id)

    if for_update:
        statement = statement.with_for_update()

    result = await session.execute(statement)
    notification = result.scalars().first()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification introuvable.",
        )

    return notification


async def list_admin_notifications(
    *,
    admin_id: UUID,
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
) -> dict[str, Any]:
    """Liste les notifications destinées à l'administrateur connecté."""

    conditions = [Notification.user_id == admin_id]
    print(f"Conditions: {conditions}")
    print(f"admin_id: {unread_only}")

    if unread_only:
        conditions.append(Notification.is_read.is_(False))

    count_result = await session.execute(
        select(func.count(Notification.id)).where(*conditions)
    )
    total = count_result.scalar_one()

    result = await session.execute(
        select(Notification)
        .where(*conditions)
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    notifications = result.scalars().all()

    unread_result = await session.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == admin_id,
            Notification.is_read.is_(False),
        )
    )
    unread_count = unread_result.scalar_one()

    return {
        "items": [
            _notification_to_dict(notification)
            for notification in notifications
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
        "unread_count": unread_count,
    }

async def create_admin_notification(
    *,
    user_id: UUID,
    notification_type: Any,
    title: str,
    message: str,
    action_url: str | None,
    session: AsyncSession,
) -> dict[str, Any]:
    """Crée une notification pour un utilisateur."""

    title = title.strip()
    message = message.strip()
    action_url = action_url.strip() if action_url else None

    if not title or not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le titre et le message sont obligatoires.",
        )

    user_result = await session.execute(
        select(User.id).where(User.id == user_id)
    )

    if user_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur destinataire introuvable.",
        )

    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        action_url=action_url,
        is_read=False,
    )

    try:
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return _notification_to_dict(notification)

    except Exception:
        await session.rollback()
        raise


async def get_admin_notification(
    *,
    notification_id: UUID,
    admin_id: UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Consulte une notification appartenant à l'administrateur."""

    notification = await _get_notification(
        notification_id=notification_id,
        user_id=admin_id,
        session=session,
    )

    return _notification_to_dict(notification)


async def mark_admin_notification_as_read(
    *,
    notification_id: UUID,
    admin_id: UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Marque une notification de l'administrateur comme lue."""

    try:
        notification = await _get_notification(
            notification_id=notification_id,
            user_id=admin_id,
            session=session,
            for_update=True,
        )

        if not notification.is_read:
            notification.is_read = True

            # read_at est un TIMESTAMP WITHOUT TIME ZONE
            # dans le schéma de base actuellement connu.
            notification.read_at = datetime.now(
                timezone.utc
            ).replace(tzinfo=None)

            await session.commit()
            await session.refresh(notification)

        return _notification_to_dict(notification)

    except Exception:
        await session.rollback()
        raise


async def mark_all_admin_notifications_as_read(
    *,
    admin_id: UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Marque toutes les notifications non lues de l'administrateur."""

    try:
        result = await session.execute(
            select(Notification)
            .where(
                Notification.user_id == admin_id,
                Notification.is_read.is_(False),
            )
            .with_for_update()
        )

        notifications = result.scalars().all()

        read_at = datetime.now(timezone.utc).replace(tzinfo=None)

        for notification in notifications:
            notification.is_read = True
            notification.read_at = read_at

        await session.commit()

        return {
            "message": "Notifications marquées comme lues.",
            "updated_count": len(notifications),
        }

    except Exception:
        await session.rollback()
        raise


async def delete_admin_notification(
    *,
    notification_id: UUID,
    admin_id: UUID,
    session: AsyncSession,
) -> None:
    """Supprime une notification appartenant à l'administrateur."""

    try:
        notification = await _get_notification(
            notification_id=notification_id,
            user_id=admin_id,
            session=session,
            for_update=True,
        )

        await session.delete(notification)
        await session.commit()

    except Exception:
        await session.rollback()
        raise