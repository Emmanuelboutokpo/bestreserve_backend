from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User

from app.schemas.account import (
    AccountDeleteRequest,
    AccountProfilePatch,
    PasswordChangeRequest,
)
from app.schemas.auth import UserPublic
from app.services.account import AccountService


admin_account_router = APIRouter(
    prefix="/accounts",
    tags=["Administration - Comptes utilisateurs"],
    dependencies=[Depends(require_admin)],
)

account_service = AccountService()


@admin_account_router.patch("/{user_id}", response_model=UserPublic)
async def admin_update_user(
    user_id: UUID,
    data: AccountProfilePatch,
    session: AsyncSession = Depends(get_session),
):
    return await account_service.admin_update_profile(
        user_id=user_id,
        data=data,
        session=session,
    )


@admin_account_router.delete("/{user_id}")
async def admin_delete_user(
    user_id: UUID,
    data: AccountDeleteRequest,
    session: AsyncSession = Depends(get_session),
):
    return await account_service.admin_delete_account(
        user_id=user_id,
        data=data,
        session=session,
    )


@admin_account_router.put("/{user_id}/password")
async def admin_change_user_password(
    user_id: UUID,
    data: PasswordChangeRequest,
    session: AsyncSession = Depends(get_session),
):
    return await account_service.admin_change_password(
        user_id=user_id,
        data=data,
        session=session,
    )


@admin_account_router.post(
    "/{user_id}/avatar",
    dependencies=[Depends(require_admin)]
)
async def admin_upload_user_avatar(
    user_id: UUID,
    avatar: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.admin_upload_avatar(
        user_id,
        avatar,
        session
    )

@admin_account_router.delete("/{user_id}/avatar", response_model=UserPublic)
async def admin_delete_user_avatar(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await account_service.admin_delete_avatar(
        user_id=user_id,
        session=session,
    )

@admin_account_router.get("/me", response_model=UserPublic)
async def get_admin_me(
    current_user: User = Depends(require_admin),
):
    return current_user