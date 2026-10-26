from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from decimal import Decimal


class Settings(BaseSettings):

    # =========================
    # DATABASE
    # =========================

    database_url: str


    # =========================
    # JWT
    # =========================

    secret_key: str 
    algorithm: str = "HS256"

    access_token_expiration_minutes: int = 30
    refresh_token_expiration_days: int = 7

    jti_expiration_seconds: int = 900

    resend_api_key: str

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    frontend_url: str

    facebook_app_id: str | None = None
    facebook_app_secret: str | None = None

    fedapay_api_key: str | None = None
    fedapay_webhook_secret: str | None = None
    fedapay_environment: str = "sandbox"
    
    push_encryption_key: str | None = None
    webpush_vapid_public_key: str | None = None
    webpush_vapid_private_key: str | None = None
    webpush_vapid_subject: str | None = None

    # =========================
    # CLOUDINARY
    # =========================

    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

    redis_host: str
    redis_port: int
    # =========================
    # KKIAPAY
    # =========================

    # =========================
    # APPLICATION
    # =========================

    rate_limit: int = 100

    cache_expiration_seconds: int = 3600

    max_top_tailors_limit: int = 10

    default_pagination_limit: int = 20


    SERVICE_FEE_PERCENT: Decimal = Decimal("5.0")

    COMMISSION_HEBERGEMENT_PERCENT: Decimal = Decimal("10.0")
    COMMISSION_RESTAURANT_PERCENT: Decimal = Decimal("0.0")
    COMMISSION_LOISIR_PERCENT: Decimal = Decimal("0.0")

    TAX_HEBERGEMENT_PERCENT: Decimal = Decimal("5.0")
    TAX_RESTAURANT_PERCENT: Decimal = Decimal("5.0")
    TAX_LOISIR_PERCENT: Decimal = Decimal("5.0")


        # =========================
    # KKIAPAY
    # =========================

    kkiapay_public_key: str | None = None
    kkiapay_private_key: str | None = None
    kkiapay_secret_key: str | None = None
    kkiapay_sandbox: bool = True
    kkiapay_webhook_secret: str | None = None



    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()