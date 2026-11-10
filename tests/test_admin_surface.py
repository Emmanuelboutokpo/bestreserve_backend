from app.main import app


def test_admin_establishment_endpoints_are_read_only():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/admin/establishments"]) == {"get"}
    assert set(paths["/api/v1/admin/establishments/{establishment_id}"]) == {
        "get"
    }


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
        paths["/api/v1/owners/establishments/{establishment_id}/amenities"]
    ) == {"post"}


def test_admin_catalog_and_global_reporting_routes_are_available():
    paths = app.openapi()["paths"]

    assert "/api/v1/admin/categories" in paths
    assert "/api/v1/admin/payments/stats" in paths
    assert "/api/v1/admin/stats/overview" in paths
    for path in (
        "/api/v1/admin/locations",
        "/api/v1/admin/amenities",
        "/api/v1/admin/reviews",
        "/api/v1/admin/subcategories",
        "/api/v1/admin/payment-conditions",
    ):
        assert path not in paths


def test_admin_users_support_partner_operations_and_owner_relationships():
    schema = app.openapi()
    paths = schema["paths"]

    assert set(paths["/api/v1/admin/users"]) == {"get", "post"}
    assert set(paths["/api/v1/admin/users/{user_id}"]) == {
        "get",
        "patch",
        "delete",
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
