import random
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.cores.redis import (
    add_jti_to_blacklist,
    delete_otp,
    delete_reset_token,
    get_email_from_reset_token,
    get_otp,
    get_resend_cooldown,
    save_otp,
    save_reset_token,
    set_resend_cooldown,
)

from app.dependencies.dependencies import (
    AccessTokenBearer,
    RefreshTokenBearer,
)

from app.emails.email import (
    send_confirmation_email,
    send_otp_email,
    send_reset_password_email,
)

from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserOTP,
)

from app.services.user import UserService
from app.utils import generateAccessToken, generate_password_hash


auth_router = APIRouter()
users = UserService()


# ============================================================
# SIGNUP
# ============================================================

@auth_router.post(
    "/auth/signup",
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    user_data: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):

    try:
        new_user = await users.signup(
            user_data,
            session,
        )

        # Génération OTP
        otp = f"{random.randint(100000, 999999)}"

        await save_otp(
            user_data.email,
            otp,
            expiry=300,
        )

        send_otp_email(
            user_data.email,
            otp,
        )

        return JSONResponse(
            content={
                "message": (
                    "Compte créé avec succès. "
                    "Veuillez vérifier votre email avec le code OTP."
                ),
                "user_id": str(new_user.id),
            },
            status_code=status.HTTP_201_CREATED,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================
# VERIFY OTP
# ============================================================

@auth_router.post("/auth/verify-otp")
async def verify_account(
    user_data: UserOTP,
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Vérifie l'adresse email avec le code OTP.
    """

    stored_otp = await get_otp(user_data.email)

    if stored_otp is None or stored_otp != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code invalide ou expiré.",
        )

    user = await users.get_user_by_email(
        user_data.email,
        session,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    session.add(user)

    await session.commit()
    await session.refresh(user, ["profile"])

    # Supprimer OTP
    await delete_otp(user.email)

    # Générer les tokens
    user_info = {
        "id": str(user.id),
        "role": user.role.value
        if hasattr(user.role, "value")
        else str(user.role),
        "token_version": user.token_version,
    }

    access_token = generateAccessToken(
        user_data=user_info,
    )

    refresh_token = generateAccessToken(
        user_data=user_info,
        refresh=True,
    )

    # Email de confirmation
    firstName = (
        user.profile.firstName
        if user.profile and user.profile.firstName
        else "Utilisateur"
    )

    send_confirmation_email(
        user.email,
        firstName,
    )

    return {
        "message": "Compte vérifié avec succès.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }


# ============================================================
# RESEND OTP
# ============================================================

@auth_router.post("/auth/resend-otp")
async def resend_otp(
    user_data: UserOTP,
    session: AsyncSession = Depends(get_session),
):
    """
    Renvoie un nouveau code OTP.
    """

    user = await users.get_user_by_email(
        user_data.email,
        session,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    

    cooldown = await get_resend_cooldown(
        user_data.email,
    )

    if cooldown:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Veuillez patienter 60 secondes "
                "avant de renvoyer un code."
            ),
        )

    otp = f"{random.randint(100000, 999999)}"

    await save_otp(
        user_data.email,
        otp,
        expiry=300,
    )

    await set_resend_cooldown(
        user_data.email,
        seconds=60,
    )

    send_otp_email(
        user_data.email,
        otp,
    )

    return {
        "message": "OTP renvoyé avec succès."
    }


# ============================================================
# LOGIN
# ============================================================

@auth_router.post("/auth/login")
async def login(
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Connexion avec email + mot de passe.
    """

    user = await users.login(
        login_data,
        session,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    await session.refresh(
        user,
        ["profile"],
    )

    user_info = {
        "id": str(user.id),
        "role": user.role.value
        if hasattr(user.role, "value")
        else str(user.role),
        "token_version": user.token_version,
    }

    access_token = generateAccessToken(
        user_data=user_info,
    )

    refresh_token = generateAccessToken(
        user_data=user_info,
        refresh=True,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


# ============================================================
# REFRESH TOKEN
# ============================================================

@auth_router.get("/auth/refresh_token")
async def get_new_access_token(
    token_details: dict = Depends(
        RefreshTokenBearer()
    ),
):
    """
    Génère un nouvel access token à partir
    du refresh token.
    """

    expiry_timestamp = token_details.get("exp")

    if not expiry_timestamp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide.",
        )

    if datetime.fromtimestamp(
        expiry_timestamp,
        tz=timezone.utc,
    ) <= datetime.now(timezone.utc):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expiré.",
        )

    user_data = {
        "id": token_details.get("sub"),
        "role": token_details.get("role"),
        "token_version": token_details.get("ver", 0),
    }

    new_access_token = generateAccessToken(
        user_data=user_data,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth_router.post("/auth/forgot-password")
async def forgot_password(
    user_data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Demande de réinitialisation du mot de passe.
    """

    user = await users.get_user_by_email(
        user_data.email,
        session,
    )

    # Pour éviter de révéler si un email existe,
    # on retourne volontairement le même message.
    if not user:
        return {
            "message": (
                "Si cette adresse email existe, "
                "un lien de réinitialisation sera envoyé."
            )
        }

    token = secrets.token_urlsafe(32)

    await save_reset_token(
        user_data.email,
        token,
    )

    send_reset_password_email(
        user_data.email,
        token,
    )

    return {
        "message": (
            "Si cette adresse email existe, "
            "un lien de réinitialisation sera envoyé."
        )
    }


# ============================================================
# RESET PASSWORD
# ============================================================

@auth_router.post("/auth/reset-password")
async def reset_password(
    reset_data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Réinitialisation du mot de passe.
    """

    email = await get_email_from_reset_token(
        reset_data.token,
    )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jeton invalide ou expiré.",
        )

    user = await users.get_user_by_email(
        email,
        session,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    user.password = generate_password_hash(
        reset_data.new_password
    )
    user.token_version += 1


    session.add(user)

    await session.commit()

    await delete_reset_token(
        reset_data.token
    )

    return {
        "message": "Mot de passe modifié avec succès."
    }


# ============================================================
# LOGOUT
# ============================================================

@auth_router.post("/auth/logout")
async def logout(
    token_details: dict = Depends(
        AccessTokenBearer()
    ),
):
    """
    Déconnexion.

    Le JWT courant est placé dans la blacklist Redis.
    """

    jti = token_details.get("jti")

    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalide.",
        )

    expiry_timestamp = token_details.get("exp")
    current_timestamp = int(datetime.now(timezone.utc).timestamp())
    if not isinstance(expiry_timestamp, int) or expiry_timestamp <= current_timestamp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré.",
        )

    await add_jti_to_blacklist(
        jti,
        expires_in=expiry_timestamp - current_timestamp,
    )

    return {
        "message": "Déconnexion réussie."
    }
