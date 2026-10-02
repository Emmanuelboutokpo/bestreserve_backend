from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select
from typing import Any, List
from uuid import UUID
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, Request, status, HTTPException
from app.utils import decode_access_token
from app.models.user import User
from app.models.enums import UserRole, UserStatus
from app.cores.redis import token_in_blacklist
from app.cores.db import get_session

class TokenBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(
        self,
        request: Request,
        session: AsyncSession = Depends(get_session),
    ) -> dict | None:
        creds = await super().__call__(request)

        if not creds:
            return None

        token = creds.credentials
        token_data = decode_access_token(token)

        self.verify_token_data(token_data)

        token_id = token_data.get("jti")
        if not isinstance(token_id, str) or not token_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide.",
            )
        if await token_in_blacklist(token_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide ou expiré.",
            )

        try:
            user_id = UUID(token_data.get("sub"))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide.",
            )

        result = await session.execute(
            select(User).where(
                User.id == user_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalars().first()
        role = user.role.value if user and hasattr(user.role, "value") else None
        if (
            not user
            or user.status != UserStatus.ACTIF
            or user.token_version != token_data.get("ver", 0)
            or role != token_data.get("role")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide ou compte indisponible.",
            )

        return token_data
    
    def valide_token(self, token: str) -> bool:
         token_data = decode_access_token(token)
         return token_data is not None

    def verify_token_data(self, token_data: dict) -> bool:
        raise NotImplementedError("Subclasses must implement this method")
    
class AccessTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: dict) -> None:
        if token_data and token_data.get('refresh'):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Please provide a valid access token')


class RefreshTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: dict) -> None:
        if token_data and not token_data.get('refresh'):
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail='Please provide a valid refresh token')

async def get_current_user(
    token_details: dict = Depends(AccessTokenBearer()),
    session: AsyncSession = Depends(get_session),
):
    subject = token_details.get("sub")

    try:
        user_id = UUID(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide.",
        )

    statement = (
        select(User)
        .options(selectinload(User.profile))
        .where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    result = await session.execute(statement)
    user = result.scalars().first()

    if not user or user.status != UserStatus.ACTIF:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte indisponible.",
        )

    return user


def require_client(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette action est réservée aux clients.",
        )
    return current_user


class RoleChecker:
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> Any:
        if current_user.role in self.allowed_roles:
            return True

        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='You do not have enough permissions to perform this action')