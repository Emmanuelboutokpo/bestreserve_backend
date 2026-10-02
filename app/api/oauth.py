import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.schemas.auth import (
    FacebookOAuthRequest,
    GoogleOAuthRequest,
    UserPublic,
)
from app.services.oauth import OAuthService
from app.utils import generateAccessToken


oauth_router = APIRouter(
    prefix="/auth",
    tags=["OAuth"],
)

oauth_service = OAuthService()


async def _create_auth_response(user) -> dict:
    user_info = {
        "id": str(user.id),
        "role": user.role.value, 
        "token_version": user.token_version,
    }

    return {
        "access_token": generateAccessToken(user_info),
        "refresh_token": generateAccessToken(
            user_info,
            refresh=True,
        ),
        "token_type": "bearer",
        "user": UserPublic.model_validate(user),
    }


@oauth_router.post("/google", response_model=dict)
async def google_login(
    data: GoogleOAuthRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Authentification avec Google.

    Le frontend envoie le ID token obtenu auprès de Google.
    Le backend vérifie ce token auprès de Google puis
    crée ou récupère le compte BestRev.
    """

    try:
        user = await oauth_service.authenticate_google(
            id_token=data.id_token,
            session=session,
        )

        return await _create_auth_response(user)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de communiquer avec Google.",
        ) from exc


@oauth_router.post("/facebook", response_model=dict)
async def facebook_login(
    data: FacebookOAuthRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Authentification avec Facebook.

    Le frontend envoie le access token Facebook.
    Le backend vérifie le token puis récupère
    les informations du compte Facebook.
    """

    try:
        user = await oauth_service.authenticate_facebook(
            access_token=data.access_token,
            session=session,
        )

        return await _create_auth_response(user)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton Facebook invalide ou expiré.",
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de communiquer avec Facebook.",
        ) from exc