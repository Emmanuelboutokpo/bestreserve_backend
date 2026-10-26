import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User


# ---------------------------------------------------------------------------
# Fixture : un vrai admin en base, avec un email de test unique
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_admin():
    """Crée un vrai admin en base, le supprime après."""
    session_gen = get_session()
    session = await session_gen.__anext__()

    admin = None
    try:
        admin = User(
            email="test-admin@bestreserv-test.local",   
            password="test-only-password",             
            # adaptez selon votre modèle : role, status, provider, etc.
            # role=UserRole.CLIENT,
            # status=UserStatus.ACTIF,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

        yield admin

    finally:
        # Nettoyage dans tous les cas, même si le test échoue
        try:
            if admin is not None and admin.id is not None:
                await session.delete(admin)
                await session.commit()
        except Exception:
            await session.rollback()
        finally:
            await session_gen.aclose()


# ---------------------------------------------------------------------------
# Override : require_admin retourne le VRAI admin en base
# ---------------------------------------------------------------------------
@pytest.fixture
def override_admin(test_admin):
    """
    Remplace require_admin par un callable qui retourne le VRAI admin
    (son UUID existe en base → la FK activity_logs.user_id est respectée).
    """
    def _fake_admin() -> User:
        return test_admin

    app.dependency_overrides[require_admin] = _fake_admin
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Le test
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_upload_multiple_photos(override_admin):
    """Vérifie que l'endpoint accepte plusieurs fichiers et les enregistre."""

    fake_cloudinary_response = {
        "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/test.jpg",
        "public_id": "bestreserv/establishments/test",
    }

    with patch(
        "app.api.admin.establishment_media.upload_image",
        new=AsyncMock(return_value=fake_cloudinary_response),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            files = [
                ("files", ("photo1.jpg", b"\xff\xd8\xff\xe0fake-jpeg", "image/jpeg")),
                ("files", ("photo2.png", b"\x89PNG\r\n\x1a\nfake-png", "image/png")),
            ]

            response = await client.post(
                "/admin/establishments/d81e7d43-d075-4916-a46b-2201d5bf671b/photos",
                files=files,
            )

            print("STATUS:", response.status_code)
            print("BODY:", response.text)

            assert response.status_code == 201, response.text
            data = response.json()
            assert data["count"] == 2