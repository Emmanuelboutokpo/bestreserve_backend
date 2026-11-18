from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.main import app


def test_admin_establishment_endpoints_are_read_only():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/admin/establishments"]) == {"get"}
    assert set(paths["/api/v1/admin/establishments/{establishment_id}"]) == {
        "get"
    }


def test_admin_manages_restaurants_and_leisure_establishments():
    paths = app.openapi()["paths"]
    managed = "/api/v1/admin/managed-establishments"

    assert set(paths[managed]) == {"get", "post"}
    assert set(paths[f"{managed}/{{establishment_id}}"]) == {
        "get",
        "patch",
        "delete",
    }
    assert f"{managed}/{{establishment_id}}/status" not in paths
    assert set(
        paths[f"{managed}/{{establishment_id}}/availability"]
    ) == {"patch"}


@pytest.mark.anyio
async def test_admin_managed_establishment_starts_published():
    from app.api.admin import managed_establishments
    from app.models.enums import EstablishmentStatus
    from app.schemas.establishment import EstablishmentCreate

    service = managed_establishments.establishment_service
    session = SimpleNamespace(
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    actor = SimpleNamespace(id=uuid4())
    request = SimpleNamespace(client=None, headers={})
    data = EstablishmentCreate(
        category_id=uuid4(),
        location_id=uuid4(),
        address="Adresse",
        name="Restaurant de test",
    )

    with (
        patch.object(
            managed_establishments,
            "validate_admin_managed_category",
            new=AsyncMock(return_value="restaurant"),
        ),
        patch.object(
            service,
            "_validate_references",
            new=AsyncMock(),
        ),
        patch.object(
            service,
            "_slugify",
            return_value="restaurant-de-test",
        ),
        patch.object(service, "_ensure_slug", new=AsyncMock()),
        patch.object(service, "_audit", new=Mock()),
    ):
        establishment = await managed_establishments.create_managed_establishment(
            data,
            request,
            actor,
            session,
        )

    assert establishment.status == EstablishmentStatus.PUBLIE
    session.commit.assert_awaited_once()


def test_admin_owner_application_review_endpoints_are_available():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/admin/owner-applications"]) == {"get"}
    assert set(
        paths["/api/v1/admin/owner-applications/{application_id}"]
    ) == {"get", "patch"}


def test_owner_can_only_manage_establishment_amenity_links():
    paths = app.openapi()["paths"]

    assert "/api/v1/owners/amenities" not in paths
    assert "/api/v1/owners/subcategories/{subcategory_id}" not in paths
    assert "/api/v1/owners/locations" not in paths
    assert set(
        paths["/api/v1/owners/categories/{category_id}/subcategories"]
    ) == {"post"}
    assert set(
        paths["/api/v1/owners/establishments/{establishment_id}/amenities"]
    ) == {"post"}


def test_admin_catalog_and_global_reporting_routes_are_available():
    paths = app.openapi()["paths"]

    assert "/api/v1/admin/categories" in paths
    assert "/api/v1/admin/payments/stats" in paths
    assert "/api/v1/admin/stats/overview" in paths
    assert set(paths["/api/v1/admin/locations"]) == {"post"}
    assert set(paths["/api/v1/admin/amenities"]) == {"post"}
    assert "/api/v1/admin/reviews" not in paths
    for path in ("/api/v1/admin/subcategories",):
        assert path not in paths
    assert "/api/v1/admin/payment-conditions" in paths
    assert (
        "/api/v1/admin/establishments/{establishment_id}/photos"
        in paths
    )
    assert (
        "/api/v1/admin/establishments/{establishment_id}/amenities"
        in paths
    )
    assert "/api/v1/admin/reservations" in paths


def test_owner_account_me_route_is_read_only():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/owners/accounts/me"]) == {"get"}


def test_admin_can_manage_own_account_profile_password_and_avatar():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/admin/accounts/me"]) == {"get", "patch"}
    assert set(paths["/api/v1/admin/accounts/me/password"]) == {"put"}
    assert set(paths["/api/v1/admin/accounts/me/avatar"]) == {
        "post",
        "delete",
    }
    assert "/api/v1/accounts/me" not in paths or set(
        paths["/api/v1/accounts/me"]
    ) == {"get", "patch"}
    assert "/api/v1/admin/accounts/{user_id}" not in paths


def test_admin_category_write_routes_accept_uploaded_images():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/admin/categories"]) == {"post"}
    assert set(paths["/api/v1/admin/categories/{category_id}"]) == {
        "patch",
        "delete",
    }
    assert set(
        paths["/api/v1/admin/categories/{category_id}/image"]
    ) == {"delete"}
    for path, method in (
        ("/api/v1/admin/categories", "post"),
        ("/api/v1/admin/categories/{category_id}", "patch"),
    ):
        request_body = paths[path][method]["requestBody"]
        assert "multipart/form-data" in request_body["content"]


def test_admin_users_support_partner_operations_and_owner_relationships():
    schema = app.openapi()
    paths = schema["paths"]

    assert set(paths["/api/v1/admin/users"]) == {"get", "post"}
    assert set(paths["/api/v1/admin/users/{user_id}"]) == {
        "get",
        "patch",
    }
    assert set(paths["/api/v1/admin/users/{user_id}/status"]) == {"patch"}
    assert "/api/v1/admin/users/{user_id}/role" not in paths
    for path in (
        "/api/v1/admin/users/{user_id}/reservations",
        "/api/v1/admin/users/{user_id}/favorites",
        "/api/v1/admin/users/{user_id}/activity",
    ):
        assert path not in paths
    assert "establishments" in schema["components"]["schemas"][
        "AdminUserAdminPublic"
    ]["properties"]
    assert "owners" in schema["components"]["schemas"][
        "AdminUserAdminPublic"
    ]["properties"]


def test_owners_keep_scoped_client_management_and_history_endpoints():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/owners/users"]) == {"get", "post"}
    assert set(paths["/api/v1/owners/users/{user_id}"]) == {
        "get",
        "patch",
        "delete",
    }
    assert "/api/v1/owners/users/{user_id}/role" not in paths
    assert "/api/v1/owners/users/{user_id}/reservations" in paths
    assert "/api/v1/owners/users/{user_id}/favorites" in paths
    assert "/api/v1/owners/users/{user_id}/activity" in paths


def test_reservation_creation_requires_an_idempotency_key():
    parameters = app.openapi()["paths"]["/reservations"]["post"]["parameters"]
    idempotency_header = next(
        parameter
        for parameter in parameters
        if parameter["name"] == "Idempotency-Key"
    )

    assert idempotency_header["required"] is True
    assert idempotency_header["schema"]["minLength"] == 16
