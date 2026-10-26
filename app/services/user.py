from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from ..models import enums 
from app.schemas.auth import RegisterRequest, LoginRequest
from app.models import User as UserModel, Profile
from app.utils import generate_password_hash, verify_password


class UserService:

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
        ):
            return None

        if not verify_password(user_data.password, user.password):
            return None

        return user