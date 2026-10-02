from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import (
    UserProvider,
    UserRole,
    UserStatus,
)


# ============================================================
# REGISTER
# ============================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isupper() for char in value):
            raise ValueError(
                "Le mot de passe doit contenir au moins une majuscule."
            )

        if not any(char.isdigit() for char in value):
            raise ValueError(
                "Le mot de passe doit contenir au moins un chiffre."
            )

        return value


# ============================================================
# LOGIN
# ============================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


# ============================================================
# GOOGLE
# ============================================================

class GoogleOAuthRequest(BaseModel):
    id_token: str
    access_token: Optional[str] = None


# ============================================================
# FACEBOOK
# ============================================================

class FacebookOAuthRequest(BaseModel):
    access_token: str


# ============================================================
# REFRESH TOKEN
# ============================================================

class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ============================================================
# LOGOUT
# ============================================================

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


# ============================================================
# FORGOT PASSWORD
# ============================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# ============================================================
# RESET PASSWORD
# ============================================================

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isupper() for char in value):
            raise ValueError(
                "Le mot de passe doit contenir au moins une majuscule."
            )

        if not any(char.isdigit() for char in value):
            raise ValueError(
                "Le mot de passe doit contenir au moins un chiffre."
            )

        return value

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError(
                "Les mots de passe ne correspondent pas."
            )

        return self


# ============================================================
# VERIFY EMAIL
# ============================================================

class VerifyEmailRequest(BaseModel):
    token: str


# ============================================================
# OTP
# ============================================================

class UserOTP(BaseModel):
    email: EmailStr


# ============================================================
# PROFILE PUBLIC
# ============================================================

class ProfilePublic(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    firstName: Optional[str] = None
    lastName: Optional[str] = None
    img: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    language: str = "fr"
    currency: str = "XOF"


# ============================================================
# USER PUBLIC
# ============================================================

class UserPublic(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    status: UserStatus
    provider: UserProvider
    profile: Optional[ProfilePublic] = None


# ============================================================
# AUTH RESPONSE
# ============================================================

class AuthResponse(BaseModel):
    success: bool = True
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user: UserPublic