from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.admin.admin_users import admin_user_router
from app.api.account import account_router
from app.api.categories import categories_router
from app.api.subcategories import subcategories_router

from app.api.amenities import (
    admin_amenities_router,
    admin_establishment_amenities_router,
    amenities_router,
)

from app.api.establishments import establishments_router
from app.api.admin.establishments import admin_establishments_router
from app.api.admin.establishment_media import establishment_media_router

from app.api.admin import (
    admin_categories_router,
    admin_subcategories_router,
)

from app.api.favorites import favorites_router

from app.api.locations import locations_router
from app.api.admin.locations import admin_locations_router

from app.api.reservations import reservations_router
from app.api.admin.reservations import admin_reservations_router
from app.api.payments import payments_router
from app.api.admin.payments import admin_payments_router
from app.api.admin.admin_notifications import admin_notifications_router
from app.api.reviews import reviews_router
from app.api.admin.reviews import admin_reviews_router

from app.api.user import auth_router
from app.api.oauth import oauth_router
from app.cores.db import engine, init_db
from app.cores.redis import token_blacklist

from app.api.admin import stats_router


origins = [
    "http://localhost:3000",
    "https://ton-domaine.com",
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Démarrage de l'application...")
    await init_db()
    yield
    print("Arrêt de l'application...")
    await engine.dispose()

app = FastAPI(
    title="BestReserv API",
    description="L'API de BestReserv pour la gestion des réservations et des utilisateurs", 
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


@app.middleware("http")
async def maintenance_mode_gate(request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    try:
        maintenance_enabled = (
            await token_blacklist.get("settings:maintenance:enabled") == "1"
        )
    except Exception:
        maintenance_enabled = False

    path = request.url.path
    allowed_during_maintenance = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh_token",
        "/api/v1/auth/logout",
        "/api/v1/payments/webhook/fedapay",
        "/api/v1/health",
        "/api/v1/version",
    }
    is_admin_path = path.startswith("/api/v1/admin/")
    if (
        maintenance_enabled
        and path.startswith("/api/v1/")
        and path not in allowed_during_maintenance
        and not is_admin_path
    ):
        return JSONResponse(
            status_code=503,
            content={"detail": "Maintenance en cours. Réessayez ultérieurement."},
            headers={"Retry-After": "60"},
        )
    return await call_next(request)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(oauth_router, prefix="/api/v1")
app.include_router(admin_user_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")
app.include_router(locations_router, prefix="/api/v1")
app.include_router(admin_locations_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(subcategories_router, prefix="/api/v1")
app.include_router(admin_categories_router, prefix="/api/v1")
app.include_router(admin_subcategories_router, prefix="/api/v1")

app.include_router(establishments_router)
app.include_router(admin_establishments_router)
app.include_router(establishment_media_router)

app.include_router(amenities_router)
app.include_router(admin_amenities_router)
app.include_router(admin_establishment_amenities_router)

app.include_router(favorites_router, prefix="/api/v1")

app.include_router(reservations_router)
app.include_router(admin_reservations_router)
app.include_router(payments_router, prefix="/api/v1")
app.include_router(admin_payments_router, prefix="/api/v1")
app.include_router(admin_notifications_router, prefix="/api/v1")
app.include_router(reviews_router)
app.include_router(admin_reviews_router)
app.include_router(stats_router, prefix="/api/v1")
