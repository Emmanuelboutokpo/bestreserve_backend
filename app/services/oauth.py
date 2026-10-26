import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.config import settings
from app.models import Profile, User
from app.models.enums import UserProvider, UserRole, UserStatus


class OAuthService:

    google_token_info_url = (
        "https://oauth2.googleapis.com/tokeninfo"
    )

    facebook_graph_url = (
        "https://graph.facebook.com/v22.0"
    )

    # ============================================================
    # GOOGLE
    # ============================================================

    async def verify_google_identity(self, id_token: str) -> dict:
        if not settings.google_client_id:
            raise RuntimeError(
                "GOOGLE_CLIENT_ID n'est pas configuré."
            )

        async with httpx.AsyncClient(timeout=10) as client:

            response = await client.get(
                self.google_token_info_url,
                params={
                    "id_token": id_token,
                },
            )

        if response.status_code != 200:
            raise ValueError(
                "Jeton Google invalide ou expiré."
            )

        claims = response.json()

        # --------------------------------------------------------
        # Vérification du token Google
        # --------------------------------------------------------

        audience = claims.get("aud")
        issuer = claims.get("iss")
        email = claims.get("email")
        email_verified = claims.get("email_verified")
        google_id = claims.get("sub")

        if (
            audience != settings.google_client_id
            or issuer not in {
                "accounts.google.com",
                "https://accounts.google.com",
            }
            or str(email_verified).lower() != "true"
            or not email
            or not google_id
        ):
            raise ValueError(
                "Jeton Google invalide ou non vérifié."
            )

        return claims

    async def authenticate_google(
        self,
        id_token: str,
        session: AsyncSession,
    ) -> User:
        claims = await self.verify_google_identity(id_token)

        return await self._get_or_create_user(
            email=claims["email"],
            provider=UserProvider.GOOGLE,
            firstName=claims.get("given_name"),
            lastName=claims.get("family_name"),
            img=claims.get("picture"),
            session=session,
        )

    # ============================================================
    # FACEBOOK
    # ============================================================

    async def verify_facebook_identity(self, access_token: str) -> dict:
        if (
            not settings.facebook_app_id
            or not settings.facebook_app_secret
        ):
            raise RuntimeError(
                "FACEBOOK_APP_ID et FACEBOOK_APP_SECRET "
                "ne sont pas configurés."
            )

        async with httpx.AsyncClient(timeout=10) as client:

            debug_response = await client.get(
                f"{self.facebook_graph_url}/debug_token",
                params={
                    "input_token": access_token,
                    "access_token": (
                        f"{settings.facebook_app_id}|"
                        f"{settings.facebook_app_secret}"
                    ),
                },
            )

            debug_response.raise_for_status()

            token_data = (
                debug_response
                .json()
                .get("data", {})
            )

            if token_data.get("is_valid") is not True:
                raise ValueError(
                    "Jeton Facebook invalide ou expiré."
                )

            if (
                str(token_data.get("app_id"))
                != settings.facebook_app_id
            ):
                raise ValueError(
                    "Le jeton Facebook n'appartient pas "
                    "à cette application."
                )

            facebook_user_id = token_data.get("user_id")

            if not facebook_user_id:
                raise ValueError(
                    "Facebook n'a pas fourni "
                    "d'identifiant utilisateur."
                )

            profile_response = await client.get(
                f"{self.facebook_graph_url}/me",
                params={
                    "fields": "id,email,first_name,last_name,picture",
                    "access_token": access_token,
                },
            )

            profile_response.raise_for_status()

            profile_data = profile_response.json()

        email = profile_data.get("email")
        facebook_id = profile_data.get("id")
        if not email or not facebook_id or facebook_id != facebook_user_id:
            raise ValueError(
                "Jeton Facebook invalide ou adresse email indisponible."
            )

        picture = (
            profile_data
            .get("picture", {})
            .get("data", {})
            .get("url")
        )

        return {
            "email": email,
            "sub": facebook_id,
            "firstName": profile_data.get("first_name"),
            "lastName": profile_data.get("last_name"),
            "img": picture,
        }

    async def authenticate_facebook(
        self,
        access_token: str,
        session: AsyncSession,
    ) -> User:
        identity = await self.verify_facebook_identity(access_token)

        return await self._get_or_create_user(
            email=identity["email"],
            provider=UserProvider.FACEBOOK,
            firstName=identity["firstName"],
            lastName=identity["lastName"],
            img=identity["img"],
            session=session,
        )

    # ============================================================
    # GET OR CREATE USER
    # ============================================================

    async def _get_or_create_user(
        self,
        email: str,
        provider: UserProvider,
        firstName: str | None,
        lastName: str | None,
        img: str | None,
        session: AsyncSession,
    ) -> User:

        result = await session.execute(
            select(User).where(
                User.email == email
            )
        )

        existing_user = result.scalars().first()

        if existing_user:
            if existing_user.provider != provider:
                raise ValueError(
                    "Cette adresse email est déjà associée "
                    "à un autre mode de connexion."
                )
            if (
                existing_user.status != UserStatus.ACTIF
                or existing_user.deleted_at is not None
            ):
                raise ValueError("Ce compte est indisponible.")

            await session.refresh(
                existing_user,
                ["profile"],
            )

            return existing_user

        user = User(
            email=email,
            password=None,
            role=UserRole.CLIENT,
            status=UserStatus.ACTIF,
            provider=provider,
        )
        session.add(user)

        await session.flush()

        profile = Profile(
            user_id=user.id,
            firstName=firstName,
            lastName=lastName,
            img=img,
        )

        session.add(profile)

        await session.commit()

        await session.refresh(
            user,
            ["profile"],
        )

        return user