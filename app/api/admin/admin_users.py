from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import (
    ActivityLog,
    Favorite,
    Reservation,
    User,
    Profile,
)
from app.models.enums import UserRole, UserStatus
from app.schemas.admin_user import (
    AdminActivityPublic,
    AdminFavoritePublic,
    AdminReservationPublic,
    AdminUserCreate,
    AdminUserPage,
    AdminUserPatch,
    AdminUserRoleUpdate,
    AdminUserStats,
    AdminUserStatusUpdate,
)
from app.schemas.auth import UserPublic
from app.utils import generate_password_hash


admin_user_router = APIRouter(
    prefix="/admin/users",
    tags=["Administration des utilisateurs"],
    dependencies=[Depends(require_admin)],
)


async def _get_active_user(user_id: UUID, session: AsyncSession) -> User:
    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )
    return user


async def _lock_active_admins(session: AsyncSession) -> int:
    result = await session.execute(
        select(User.id)
        .where(
            User.role == UserRole.ADMIN,
            User.status == UserStatus.ACTIF,
        )
        .order_by(User.id)
        .with_for_update()
    )
    
    return len(result.scalars().all())


async def _protect_last_admin(user: User, session: AsyncSession) -> None:
    if (
        user.role == UserRole.ADMIN
        and user.status == UserStatus.ACTIF
        and await _lock_active_admins(session) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de désactiver ou rétrograder le dernier administrateur actif.",
        )


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


@admin_user_router.get("", response_model=AdminUserPage)
async def list_users(
    search: str | None = Query(default=None, min_length=1, max_length=255),
    role: UserRole | None = None,
    user_status: UserStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if user_status is not None:
        filters.append(User.status == user_status)
    if search is not None:
        search_value = search.strip()
        if not search_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le terme de recherche ne peut pas être vide.",
            )
        escaped_search = (
            search_value
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        filters.append(User.email.ilike(f"%{escaped_search}%", escape="\\"))

    count_result = await session.execute(
        select(func.count(User.id)).where(*filters)
    )
    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(*filters)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": result.scalars().all(),
        "total": count_result.scalar_one(),
        "limit": limit,
        "offset": offset,
    }


@admin_user_router.get("/stats", response_model=AdminUserStats)
async def get_user_stats(session: AsyncSession = Depends(get_session)):
    created_after = datetime.now(timezone.utc) - timedelta(days=30)
    conditions = {
        "total": User.id.isnot(None),
        "active": (User.id.isnot(None), User.status == UserStatus.ACTIF),
        "inactive": (User.id.isnot(None), User.status == UserStatus.INACTIF),
        "pending": (User.id.isnot(None), User.status == UserStatus.EN_ATTENTE),
        "suspended": (User.id.isnot(None), User.status == UserStatus.SUSPENDU),
        "clients": (User.id.isnot(None), User.role == UserRole.CLIENT),
        "admins": (User.id.isnot(None), User.role == UserRole.ADMIN),
        "created_last_30_days": (
            User.id.isnot(None),
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


@admin_user_router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: UUID, session: AsyncSession = Depends(get_session)):
    return await _get_active_user(user_id, session)


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
        role=UserRole.CLIENT,
        status=UserStatus.EN_ATTENTE,
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
    return user


@admin_user_router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: UUID,
    data: AdminUserPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_user(user_id, session)
    changes = data.model_dump(exclude_unset=True)
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
            if user.id == actor.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Un administrateur ne peut pas modifier son propre email.",
                )
            await _protect_last_admin(user, session)
            user.email = email
            user.status = UserStatus.EN_ATTENTE
            user.token_version += 1
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
    return user


@admin_user_router.delete("/{user_id}")
async def disable_user(
    user_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_user(user_id, session)
    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un administrateur ne peut pas désactiver son propre compte.",
        )
    await _protect_last_admin(user, session)

    user.status = UserStatus.INACTIF
    user.token_version += 1
    _audit(session, actor, "ADMIN_USER_DISABLED", user, request)
    await session.commit()
    return {"message": "Utilisateur désactivé."}


@admin_user_router.patch("/{user_id}/role", response_model=UserPublic)
async def update_user_role(
    user_id: UUID,
    data: AdminUserRoleUpdate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_user(user_id, session)
    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un administrateur ne peut pas modifier son propre rôle.",
        )
    new_role = UserRole(data.role)
    if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
        await _protect_last_admin(user, session)
    if user.role != new_role:
        user.role = new_role
        user.token_version += 1

    _audit(session, actor, "ADMIN_USER_ROLE_UPDATED", user, request)
    await session.commit()
    await session.refresh(user, ["profile"])
    return user


@admin_user_router.patch("/{user_id}/status", response_model=UserPublic)
async def update_user_status(
    user_id: UUID,
    data: AdminUserStatusUpdate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_user(user_id, session)
    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un administrateur ne peut pas modifier son propre statut.",
        )
    if (
        user.role == UserRole.ADMIN
        and user.status == UserStatus.ACTIF
        and data.status != UserStatus.ACTIF
    ):
        await _protect_last_admin(user, session)
    if user.status != data.status:
        user.status = data.status
        user.token_version += 1

    _audit(session, actor, "ADMIN_USER_STATUS_UPDATED", user, request)
    await session.commit()
    await session.refresh(user, ["profile"])
    return user


@admin_user_router.get(
    "/{user_id}/reservations",
    response_model=list[AdminReservationPublic],
)
async def list_user_reservations(
    user_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    await _get_active_user(user_id, session)
    result = await session.execute(
        select(Reservation)
        .where(Reservation.user_id == user_id)
        .order_by(Reservation.created_at.desc(), Reservation.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@admin_user_router.get(
    "/{user_id}/favorites",
    response_model=list[AdminFavoritePublic],
)
async def list_user_favorites(
    user_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    await _get_active_user(user_id, session)
    result = await session.execute(
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@admin_user_router.get(
    "/{user_id}/activity",
    response_model=list[AdminActivityPublic],
)
async def list_user_activity(
    user_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    await _get_active_user(user_id, session)
    result = await session.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == user_id)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()