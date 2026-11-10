from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.cores.db import get_session
from app.cores.redis import save_otp
from app.dependencies.dependencies import require_admin
from app.emails.email import send_otp_email
from app.models import ActivityLog, User, Profile
from app.models.enums import UserRole, UserStatus
from app.schemas.admin_user import (
    AdminUserAdminPage,
    AdminUserAdminPublic,
    AdminUserCreate,
    AdminUserPatch,
    AdminUserStats,
    AdminUserStatusUpdate,
)
from app.schemas.auth import UserPublic
from app.services.user import UserService
from app.utils import generate_password_hash


admin_user_router = APIRouter(
    prefix="/admin/users",
    tags=["Administration des utilisateurs"],
    dependencies=[Depends(require_admin)],
)
user_service = UserService()


async def _get_active_user(user_id: UUID, session: AsyncSession) -> User:
    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(
            User.id == user_id,
            User.is_deleted.is_(False),
        )
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )
    return user


async def _get_active_partner(
    user_id: UUID,
    session: AsyncSession,
) -> User:
    user = await _get_active_user(user_id, session)
    if user.role != UserRole.PROPRIETAIRE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partenaire introuvable.",
        )
    return user


def _audit(
    session: AsyncSession,
    actor: User,
    action: str,
    target: User,
    request: Request,
) -> None:
    session.add(
        ActivityLog(
            user_id=actor.id,
            action=action,
            entity_type="user",
            entity_id=target.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:1000] or None,
            metadata_json={"target_user_id": str(target.id)},
        )
    )


@admin_user_router.get("", response_model=AdminUserAdminPage)
async def list_users(
    search: str | None = Query(default=None, min_length=1, max_length=255),
    role: UserRole | None = None,
    user_status: UserStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.list_admin_users(
        session,
        search=search,
        role=role,
        status_filter=user_status,
        limit=limit,
        offset=offset,
    )


@admin_user_router.get("/stats", response_model=AdminUserStats)
async def get_user_stats(session: AsyncSession = Depends(get_session)):
    created_after = datetime.now(timezone.utc) - timedelta(days=30)
    conditions = {
        "total": (User.id.isnot(None), User.is_deleted.is_(False)),
        "active": (
            User.id.isnot(None),
            User.is_deleted.is_(False),
            User.status == UserStatus.ACTIF,
        ),
        "inactive": (
            User.id.isnot(None),
            User.is_deleted.is_(False),
            User.status == UserStatus.INACTIF,
        ),
        "pending": (
            User.id.isnot(None),
            User.is_deleted.is_(False),
            User.status == UserStatus.EN_ATTENTE,
        ),
        "suspended": (
            User.id.isnot(None),
            User.is_deleted.is_(False),
            User.status == UserStatus.SUSPENDU,
        ),
        "clients": (
            User.id.isnot(None),
            User.is_deleted.is_(False),
            User.role == UserRole.CLIENT,
        ),
        "admins": (
            User.id.isnot(None),
            User.is_deleted.is_(False),
            User.role == UserRole.ADMIN,
        ),
        "created_last_30_days": (
            User.id.isnot(None),
            User.is_deleted.is_(False),
            User.created_at >= created_after,
        ),
    }
    counts = {}
    for name, criterion in conditions.items():
        clauses = criterion if isinstance(criterion, tuple) else (criterion,)
        result = await session.execute(
            select(func.count(User.id)).where(*clauses)
        )
        counts[name] = result.scalar_one()
    return counts 


@admin_user_router.get("/{user_id}", response_model=AdminUserAdminPublic)
async def get_user(user_id: UUID, session: AsyncSession = Depends(get_session)):
    return await user_service.get_admin_user(user_id, session)


@admin_user_router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    data: AdminUserCreate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    email = str(data.email).strip().lower()
    existing = await session.execute(
        select(User.id).where(func.lower(User.email) == email)
    )
    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur avec cet email existe déjà.",
        )

    user = User(
        email=email,
        password=generate_password_hash(data.password),
        role=UserRole.PROPRIETAIRE,
        status=UserStatus.ACTIF,
        email_verified=False,
        created_by=actor.id,
    )
    session.add(user)
    await session.flush()
    profile = Profile(
        user_id=user.id,
        firstName=data.firstName,
        lastName=data.lastName,
    )
    session.add(profile)
    _audit(session, actor, "ADMIN_USER_CREATED", user, request)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur avec cet email existe déjà.",
        ) from exc
    await session.refresh(user, ["profile"])
    otp = f"{secrets.randbelow(900000) + 100000}"
    await save_otp(user.email, otp, expiry=300)
    send_otp_email(user.email, otp)
    return user


@admin_user_router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: UUID,
    data: AdminUserPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_partner(user_id, session)
    changes = data.model_dump(exclude_unset=True)
    email_changed = False
    if "email" in changes:
        email = str(changes["email"]).strip().lower()
        existing = await session.execute(
            select(User.id).where(
                func.lower(User.email) == email,
                User.id != user.id,
            )
        )
        if existing.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un utilisateur avec cet email existe déjà.",
            )
        if email != user.email.casefold():
            user.email = email
            user.email_verified = False
            user.token_version += 1
            email_changed = True
        changes.pop("email")

    if changes:
        if user.profile is None:
            user.profile = Profile(user_id=user.id)
            session.add(user.profile)
        for field, value in changes.items():
            setattr(user.profile, field, value)

    _audit(session, actor, "ADMIN_USER_UPDATED", user, request)
    await session.commit()
    await session.refresh(user, ["profile"])
    if email_changed:
        otp = f"{secrets.randbelow(900000) + 100000}"
        await save_otp(user.email, otp, expiry=300)
        send_otp_email(user.email, otp)
    return user


@admin_user_router.delete("/{user_id}")
async def disable_user(
    user_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_partner(user_id, session)

    user.status = UserStatus.INACTIF
    user.token_version += 1
    _audit(session, actor, "ADMIN_USER_DISABLED", user, request)
    await session.commit()
    return {"message": "Utilisateur désactivé."}


@admin_user_router.patch("/{user_id}/status", response_model=UserPublic)
async def update_user_status(
    user_id: UUID,
    data: AdminUserStatusUpdate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_partner(user_id, session)
    if user.status != data.status:
        user.status = data.status
        user.token_version += 1

    _audit(session, actor, "ADMIN_USER_STATUS_UPDATED", user, request)
    await session.commit()
    await session.refresh(user, ["profile"])
    return user
