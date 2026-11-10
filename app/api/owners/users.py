from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.cores.db import get_session
from app.dependencies.dependencies import require_proprietaire
from app.models import (
    ActivityLog,
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
    AdminUserStats,
    AdminUserStatusUpdate,
)
from app.schemas.auth import UserPublic
from app.services import stats as stats_service
from app.services.user import UserService
from app.utils import generate_password_hash

owner_user_router = APIRouter(
    prefix="/owners/users",
    tags=["Propriétaire - Utilisateurs"],
    dependencies=[Depends(require_proprietaire)],
)

user_service = UserService()


async def _get_active_user(
    user_id: UUID,
    session: AsyncSession,
    owner_id: UUID,
) -> User:
    return await user_service.get_owner_user(user_id, owner_id, session)


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


@owner_user_router.get("", response_model=AdminUserPage)
async def list_users(
    actor: User = Depends(require_proprietaire),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    user_status: UserStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.list_owner_users(
        actor.id,
        session,
        search=search,
        status_filter=user_status,
        limit=limit,
        offset=offset,
    )


@owner_user_router.get("/stats", response_model=AdminUserStats)
async def get_user_stats(
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await stats_service.get_stats_users(
        session,
        owner_id=actor.id,
    )


@owner_user_router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: UUID,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    return await _get_active_user(user_id, session, actor.id)


@owner_user_router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    data: AdminUserCreate,
    request: Request,
    actor: User = Depends(require_proprietaire),
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


@owner_user_router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: UUID,
    data: AdminUserPatch,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_user(user_id, session, actor.id)
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
                    detail="Un propriétaire ne peut pas modifier l'email d'un client associé.",
                )
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


@owner_user_router.delete("/{user_id}")
async def disable_user(
    user_id: UUID,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_user(user_id, session, actor.id)
    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un propriétaire ne peut pas désactiver son propre compte.",
        )

    user.status = UserStatus.INACTIF
    user.token_version += 1
    _audit(session, actor, "ADMIN_USER_DISABLED", user, request)
    await session.commit()
    return {"message": "Utilisateur désactivé."}


@owner_user_router.patch("/{user_id}/status", response_model=UserPublic)
async def update_user_status(
    user_id: UUID,
    data: AdminUserStatusUpdate,
    request: Request,
    actor: User = Depends(require_proprietaire),
    session: AsyncSession = Depends(get_session),
):
    user = await _get_active_user(user_id, session, actor.id)
    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un administrateur ne peut pas modifier son propre statut.",
        )
    if user.status != data.status:
        user.status = data.status
        user.token_version += 1

    _audit(session, actor, "ADMIN_USER_STATUS_UPDATED", user, request)
    await session.commit()
    await session.refresh(user, ["profile"])
    return user


@owner_user_router.get(
    "/{user_id}/reservations",
    response_model=list[AdminReservationPublic],
)
async def list_user_reservations(
    user_id: UUID,
    actor: User = Depends(require_proprietaire),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    await _get_active_user(user_id, session, actor.id)
    return await user_service.list_owner_user_reservations(
        user_id,
        actor.id,
        session,
        limit=limit,
        offset=offset,
    )


@owner_user_router.get(
    "/{user_id}/favorites",
    response_model=list[AdminFavoritePublic],
)
async def list_user_favorites(
    user_id: UUID,
    actor: User = Depends(require_proprietaire),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    await _get_active_user(user_id, session, actor.id)
    return await user_service.list_owner_user_favorites(
        user_id,
        actor.id,
        session,
        limit=limit,
        offset=offset,
    )


@owner_user_router.get(
    "/{user_id}/activity",
    response_model=list[AdminActivityPublic],
)
async def list_user_activity(
    user_id: UUID,
    actor: User = Depends(require_proprietaire),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    await _get_active_user(user_id, session, actor.id)
    return await user_service.list_owner_user_activity(
        user_id,
        actor.id,
        session,
        limit=limit,
        offset=offset,
    )