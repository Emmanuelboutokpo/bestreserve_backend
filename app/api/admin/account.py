from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User

from app.schemas.account import (
    AccountProfilePatch,
    PasswordChangeRequest,
)
from app.schemas.auth import UserPublic
from app.services.account import AccountService


admin_account_router = APIRouter(
    prefix="/admin/accounts",
    tags=["Admin - Comptes Administrateurs"],
    dependencies=[Depends(require_admin)],
)

account_service = AccountService()


@admin_account_router.patch("/me", response_model=UserPublic)
async def admin_update_my_account(
    data: AccountProfilePatch,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.update_profile(current_user, data, session)


@admin_account_router.put("/me/password")
async def admin_change_my_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.change_password(current_user, data, session)


@admin_account_router.post("/me/avatar", response_model=UserPublic)
async def admin_upload_my_avatar(
    avatar: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.upload_avatar(current_user, avatar, session)


@admin_account_router.delete("/me/avatar", response_model=UserPublic)
async def admin_delete_my_avatar(
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await account_service.delete_avatar(current_user, session)


@admin_account_router.get("/me", response_model=UserPublic)
async def get_admin_me(
    current_user: User = Depends(require_admin),
):
    return current_user
