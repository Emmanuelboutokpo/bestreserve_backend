"""Routes d'administration des notifications BestRev."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.dependencies import require_admin, get_session
from app.models import User
from app.schemas.notifications import AdminNotificationCreate
from app.services import notification as notification_service


admin_notifications_router = APIRouter(
    prefix="/admin/notifications",
    tags=["Administration - Notifications"],
    dependencies=[Depends(require_admin)],
)


@admin_notifications_router.get(
    "",
    summary="Lister les notifications administratives",
)
async def list_admin_notifications(
    admin_user: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unread_only: bool = False,
):
    return await notification_service.list_admin_notifications(
        admin_id=admin_user.id,
        session=session,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )


@admin_notifications_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Créer une notification",
)
async def create_notification(
    data: AdminNotificationCreate,
    session: AsyncSession = Depends(get_session),
):
    return await notification_service.create_admin_notification(
        user_id=data.user_id,
        notification_type=data.type,
        title=data.title,
        message=data.message,
        action_url=data.action_url,
        session=session,
    )


@admin_notifications_router.get(
    "/{notification_id}",
    summary="Consulter une notification",
)
async def get_notification(
    notification_id: UUID,
    admin_user: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_session),
):
    return await notification_service.get_admin_notification(
        notification_id=notification_id,
        admin_id=admin_user.id,
        session=session,
    )


@admin_notifications_router.patch(
    "/read-all",
    summary="Marquer toutes les notifications comme lues",
)
async def mark_all_as_read(
    admin_user: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_session),
):
    return await notification_service.mark_all_admin_notifications_as_read(
        admin_id=admin_user.id,
        session=session,
    )


@admin_notifications_router.patch(
    "/{notification_id}/read",
    summary="Marquer une notification comme lue",
)
async def mark_as_read(
    notification_id: UUID,
    admin_user: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_session),
):
    return await notification_service.mark_admin_notification_as_read(
        notification_id=notification_id,
        admin_id=admin_user.id,
        session=session,
    )


@admin_notifications_router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une notification",
)
async def delete_notification(
    notification_id: UUID,
    admin_user: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_session),
):
    await notification_service.delete_admin_notification(
        notification_id=notification_id,
        admin_id=admin_user.id,
        session=session,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)