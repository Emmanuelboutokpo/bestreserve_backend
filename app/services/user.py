from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select
from ..models import enums 
from app.schemas.auth import RegisterRequest, LoginRequest
from app.models import (
    ActivityLog,
    Establishment,
    Favorite,
    Profile,
    Reservation,
    User as UserModel,
)
from app.models.enums import UserRole, UserStatus
from app.utils import generate_password_hash, verify_password


class UserService:

    @staticmethod
    def _admin_user_summary(
        user: UserModel,
        establishments: list[dict],
        owners: list[dict],
    ) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "provider": user.provider,
            "profile": user.profile,
            "establishments": establishments,
            "owners": owners,
        }

    async def _serialize_admin_users(
        self,
        users: list[UserModel],
        session: AsyncSession,
    ) -> list[dict]:
        owner_ids = [
            user.id for user in users if user.role == UserRole.PROPRIETAIRE
        ]
        client_ids = [
            user.id for user in users if user.role == UserRole.CLIENT
        ]

        establishments_by_owner: dict[UUID, list[dict]] = {
            owner_id: [] for owner_id in owner_ids
        }
        if owner_ids:
            establishment_result = await session.execute(
                select(Establishment)
                .join(
                    UserModel,
                    UserModel.id == Establishment.owner_id,
                )
                .where(
                    Establishment.owner_id.in_(owner_ids),
                    UserModel.role == UserRole.PROPRIETAIRE,
                    UserModel.is_deleted.is_(False),
                )
                .order_by(
                    Establishment.created_at.desc(),
                    Establishment.id.desc(),
                )
            )
            for establishment in establishment_result.scalars().all():
                establishments_by_owner[establishment.owner_id].append(
                    {
                        "id": establishment.id,
                        "name": establishment.name,
                        "slug": establishment.slug,
                        "status": establishment.status,
                    }
                )

        owners_by_client: dict[UUID, dict[UUID, dict]] = {
            client_id: {} for client_id in client_ids
        }
        if client_ids:
            owner_result = await session.execute(
                select(
                    Reservation.user_id,
                    UserModel.id,
                    UserModel.email,
                    Profile.firstName,
                    Profile.lastName,
                )
                .join(
                    Establishment,
                    Establishment.id == Reservation.establishment_id,
                )
                .join(
                    UserModel,
                    UserModel.id == Establishment.owner_id,
                )
                .outerjoin(Profile, Profile.user_id == UserModel.id)
                .where(
                    Reservation.user_id.in_(client_ids),
                    UserModel.role == UserRole.PROPRIETAIRE,
                    UserModel.is_deleted.is_(False),
                )
                .distinct()
                .order_by(UserModel.id)
            )
            for client_id, owner_id, email, first_name, last_name in (
                owner_result.all()
            ):
                owners_by_client[client_id][owner_id] = {
                    "id": owner_id,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                }

        return [
            self._admin_user_summary(
                user,
                establishments_by_owner.get(user.id, []),
                list(owners_by_client.get(user.id, {}).values()),
            )
            for user in users
        ]

    async def list_admin_users(
        self,
        session: AsyncSession,
        *,
        search: str | None = None,
        role: UserRole | None = None,
        status_filter: UserStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        filters = [UserModel.is_deleted.is_(False)]
        if role is not None:
            filters.append(UserModel.role == role)
        if status_filter is not None:
            filters.append(UserModel.status == status_filter)
        if search is not None:
            escaped_search = (
                search.strip()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            if not escaped_search:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Le terme de recherche ne peut pas être vide.",
                )
            filters.append(
                UserModel.email.ilike(
                    f"%{escaped_search}%",
                    escape="\\",
                )
            )

        count_result = await session.execute(
            select(func.count(UserModel.id)).where(*filters)
        )
        result = await session.execute(
            select(UserModel)
            .options(selectinload(UserModel.profile))
            .where(*filters)
            .order_by(UserModel.created_at.desc(), UserModel.id.desc())
            .offset(offset)
            .limit(limit)
        )
        users = result.scalars().all()
        return {
            "items": await self._serialize_admin_users(users, session),
            "total": count_result.scalar_one(),
            "limit": limit,
            "offset": offset,
        }

    async def get_admin_user(
        self,
        user_id: UUID,
        session: AsyncSession,
    ) -> dict:
        result = await session.execute(
            select(UserModel)
            .options(selectinload(UserModel.profile))
            .where(
                UserModel.id == user_id,
                UserModel.is_deleted.is_(False),
            )
        )
        user = result.scalars().first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur introuvable.",
            )
        return (await self._serialize_admin_users([user], session))[0]

    @staticmethod
    def _owner_customer_ids(owner_id: UUID):
        return (
            select(Reservation.user_id)
            .join(
                Establishment,
                Establishment.id == Reservation.establishment_id,
            )
            .where(Establishment.owner_id == owner_id)
            .distinct()
        )

    async def list_owner_users(
        self,
        owner_id: UUID,
        session: AsyncSession,
        *,
        search: str | None = None,
        status_filter: UserStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        filters = [
            UserModel.role == UserRole.CLIENT,
            UserModel.id.in_(self._owner_customer_ids(owner_id)),
        ]
        if status_filter is not None:
            filters.append(UserModel.status == status_filter)
        if search is not None:
            escaped_search = (
                search.strip()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            if not escaped_search:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Le terme de recherche ne peut pas être vide.",
                )
            filters.append(
                UserModel.email.ilike(
                    f"%{escaped_search}%",
                    escape="\\",
                )
            )

        count_result = await session.execute(
            select(func.count(UserModel.id)).where(*filters)
        )
        result = await session.execute(
            select(UserModel)
            .options(selectinload(UserModel.profile))
            .where(*filters)
            .order_by(UserModel.created_at.desc(), UserModel.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": result.scalars().all(),
            "total": count_result.scalar_one(),
            "limit": limit,
            "offset": offset,
        }

    async def get_owner_user(
        self,
        user_id: UUID,
        owner_id: UUID,
        session: AsyncSession,
    ) -> UserModel:
        result = await session.execute(
            select(UserModel)
            .options(selectinload(UserModel.profile))
            .where(
                UserModel.id == user_id,
                UserModel.role == UserRole.CLIENT,
                UserModel.id.in_(self._owner_customer_ids(owner_id)),
            )
        )
        user = result.scalars().first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur introuvable.",
            )
        return user

    async def list_owner_user_reservations(
        self,
        user_id: UUID,
        owner_id: UUID,
        session: AsyncSession,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Reservation]:
        result = await session.execute(
            select(Reservation)
            .join(
                Establishment,
                Establishment.id == Reservation.establishment_id,
            )
            .where(
                Reservation.user_id == user_id,
                Establishment.owner_id == owner_id,
            )
            .order_by(Reservation.created_at.desc(), Reservation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def list_owner_user_favorites(
        self,
        user_id: UUID,
        owner_id: UUID,
        session: AsyncSession,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Favorite]:
        result = await session.execute(
            select(Favorite)
            .join(
                Establishment,
                Establishment.id == Favorite.establishment_id,
            )
            .where(
                Favorite.user_id == user_id,
                Establishment.owner_id == owner_id,
            )
            .order_by(Favorite.created_at.desc(), Favorite.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def list_owner_user_activity(
        self,
        user_id: UUID,
        owner_id: UUID,
        session: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ActivityLog]:
        owner_reservation_ids = (
            select(Reservation.id)
            .join(
                Establishment,
                Establishment.id == Reservation.establishment_id,
            )
            .where(
                Reservation.user_id == user_id,
                Establishment.owner_id == owner_id,
            )
        )
        result = await session.execute(
            select(ActivityLog)
            .where(
                ActivityLog.user_id == user_id,
                ActivityLog.entity_type == "reservation",
                ActivityLog.entity_id.in_(owner_reservation_ids),
            )
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_user_by_email(
        self,
        email: str,
        session: AsyncSession
    ):
        statement = select(UserModel).where(
            UserModel.email == email
        )

        result = await session.execute(statement)

        return result.scalars().first()

    async def user_exists(
        self,
        email: str,
        session: AsyncSession
    ) -> bool:
        user = await self.get_user_by_email(
            email,
            session
        )

        return user is not None

    async def signup(
        self,
        data: RegisterRequest,
        session: AsyncSession
    ):
        if await self.user_exists(data.email, session):
            raise ValueError(
                "Un utilisateur avec cet email existe déjà"
            )

        try:
            # -----------------------------
            # USER
            # -----------------------------

            new_user = UserModel(
                email=data.email,
                password=generate_password_hash(
                    data.password
                ),
                role=enums.UserRole.CLIENT
            )

            session.add(new_user)

            await session.flush()

            # -----------------------------
            # PROFILE
            # -----------------------------

            new_profile = Profile(
                user_id=new_user.id
            )

            session.add(new_profile)

            # -----------------------------
            # COMMIT
            # -----------------------------

            await session.commit()

            await session.refresh(new_user)

            return new_user

        except Exception:
            await session.rollback()
            raise

    async def signup_owner(
        self,
        data: RegisterRequest,
        session: AsyncSession,
    ):
        if await self.user_exists(data.email, session):
            raise ValueError(
                "Un utilisateur avec cet email existe déjà"
            )

        try:
            owner = UserModel(
                email=data.email,
                password=generate_password_hash(data.password),
                role=UserRole.PROPRIETAIRE,
                email_verified=False,
            )
            session.add(owner)
            await session.flush()
            session.add(Profile(user_id=owner.id))
            await session.commit()
            await session.refresh(owner)
            return owner
        except Exception:
            await session.rollback()
            raise

    async def login(
        self,
        user_data: LoginRequest,
        session: AsyncSession
    ):
        statement = select(UserModel).where(
            UserModel.email == user_data.email
        )

        result = await session.execute(statement)

        user = result.scalars().first()

        if (
            not user
            or not user.password
            or user.status != enums.UserStatus.ACTIF
            or (
                user.role == UserRole.PROPRIETAIRE
                and not user.email_verified
            )
        ):
            return None

        if not verify_password(user_data.password, user.password):
            return None

        return user