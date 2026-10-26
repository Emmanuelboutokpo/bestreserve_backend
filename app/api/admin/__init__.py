from app.api.admin.categories import admin_categories_router
from app.api.admin.subcategories import admin_subcategories_router
from app.api.admin.stats import stats_router
__all__ = [
    "admin_categories_router",
    "admin_subcategories_router",
    "stats_router",
]