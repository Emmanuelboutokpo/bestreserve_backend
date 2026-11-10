from app.api.owners.owners import owner_application_router
from app.api.owners.establishments import owner_establishments_router
from app.api.owners.subcategories import owner_subcategories_router

__all__ = [
    "owner_application_router",
    "owner_establishments_router",
    "owner_subcategories_router",
]
