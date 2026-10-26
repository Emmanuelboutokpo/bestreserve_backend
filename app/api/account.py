from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    UploadFile,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import (
    get_current_user,
    require_client,
)

from app.models import User
from app.schemas.account import (
    AccountDeleteRequest,
    AccountProfilePatch,
    NotificationPage,
    PasswordChangeRequest,
)

from app.schemas.auth import UserPublic
from app.services.account import AccountService


account_router = APIRouter(
    tags=["Compte client"],
    dependencies=[Depends(require_client)],
)

account_service = AccountService()

@account_router.get("/users/me", response_model=UserPublic)
async def get_my_account(
    current_user: User = Depends(get_current_user),
):
    return current_user


@account_router.patch("/users/me", response_model=UserPublic)
async def update_my_account(
    data: AccountProfilePatch,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.update_profile(current_user, data, session)


@account_router.delete("/users/me")
async def delete_my_account(
    data: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.delete_account(current_user, data, session)


@account_router.put("/users/me/password")
async def change_my_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.change_password(current_user, data, session)


@account_router.post("/users/me/avatar", response_model=UserPublic)
async def upload_my_avatar(
    avatar: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.upload_avatar(current_user, avatar, session)


@account_router.delete("/users/me/avatar", response_model=UserPublic)
async def delete_my_avatar(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.delete_avatar(current_user, session)


@account_router.get("/users/me/notifications", response_model=NotificationPage)
async def list_my_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.list_notifications(
        current_user, session, limit=limit, offset=offset
    )


@account_router.patch("/users/me/notifications/{notification_id}/read")
async def mark_my_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.mark_notification_read(
        current_user, notification_id, session
    )


@account_router.patch("/users/me/notifications/read-all")
async def mark_all_my_notifications_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.mark_all_notifications_read(current_user, session)


@account_router.get("/users/me/notifications/unread-count")
async def get_my_unread_notification_count(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.get_unread_count(current_user, session)


@account_router.delete("/users/me/notifications/{notification_id}")
async def delete_my_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.delete_notification(
        current_user, notification_id, session
    )