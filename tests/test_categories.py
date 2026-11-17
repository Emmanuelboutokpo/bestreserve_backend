from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models import Category
from app.schemas.category import CategoryCreate, CategoryPatch, CategoryPublic
from app.services.category import CategoryService


def _image_upload(
    contents: bytes = b"\xff\xd8\xffcategory image",
    content_type: str = "image/jpeg",
) -> UploadFile:
    return UploadFile(
        filename="category.jpg",
        file=BytesIO(contents),
        headers=Headers({"content-type": content_type}),
    )


def test_category_image_is_optional_and_exposed():
    category_id = uuid4()
    category = Category(
        id=category_id,
        name="Hébergement",
    )

    assert category.img is None

    public_category = CategoryPublic.model_validate(category)
    assert public_category.img == category.img

    category_without_image = Category(
        id=uuid4(),
        name="Restaurant",
    )
    assert category_without_image.img is None


def test_category_schemas_no_longer_accept_image_urls():
    with pytest.raises(ValueError):
        CategoryCreate.model_validate(
            {"name": "Hébergement", "img": "https://example.com/image.jpg"}
        )


@pytest.mark.anyio
async def test_admin_create_category_accepts_flat_multipart_fields(monkeypatch):
    import httpx

    from app.api.admin import categories as category_api
    from app.cores.db import get_session
    from app.dependencies.dependencies import require_admin
    from app.main import app
    from app.models import User

    received = {}

    async def create_category(data, actor, request, session, *, image=None):
        received["name"] = data.name
        received["icon"] = data.icon
        received["image_filename"] = image.filename if image else None
        return Category(
            id=uuid4(),
            name=data.name,
            icon=data.icon,
            img="https://cdn.example.com/category.jpg",
        )

    monkeypatch.setattr(
        category_api.category_service,
        "create",
        create_category,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        require_admin,
        lambda: User(
            id=uuid4(),
            email="admin@example.com",
            role="ADMIN",
        ),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        get_session,
        lambda: object(),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/admin/categories",
            data={"name": "Hébergement", "icon": "home"},
            files={
                "img": (
                    "category.jpg",
                    b"\xff\xd8\xffcategory image",
                    "image/jpeg",
                )
            },
        )

    assert response.status_code == 201
    assert received == {
        "name": "Hébergement",
        "icon": "home",
        "image_filename": "category.jpg",
    }


@pytest.mark.anyio
async def test_category_image_upload_validates_format_and_size():
    contents = await CategoryService._read_image(_image_upload())
    assert contents == b"\xff\xd8\xffcategory image"

    with pytest.raises(HTTPException) as invalid_format:
        await CategoryService._read_image(
            _image_upload(b"not an image", "image/jpeg")
        )
    assert invalid_format.value.status_code == 415

    with pytest.raises(HTTPException) as too_large:
        await CategoryService._read_image(
            _image_upload(
                b"\xff\xd8\xff" + b"x" * CategoryService.MAX_IMAGE_BYTES,
            )
        )
    assert too_large.value.status_code == 413


@pytest.mark.anyio
async def test_category_service_uploads_and_replaces_image(monkeypatch):
    service = CategoryService()
    actor = SimpleNamespace(id=uuid4())
    request = SimpleNamespace(client=None, headers={})
    image_url = "https://res.cloudinary.com/demo/image/upload/bestreserv/categories/stay.jpg"
    upload_image = AsyncMock(
        return_value={
            "secure_url": image_url,
            "public_id": "bestreserv/categories/stay",
        }
    )
    destroy_image = AsyncMock()
    monkeypatch.setattr("app.services.category.upload_image", upload_image)
    monkeypatch.setattr("app.services.category.destroy_image", destroy_image)

    create_session = SimpleNamespace(
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    await service.create(
        CategoryCreate(name="Hébergement"),
        actor,
        request,
        create_session,
        image=_image_upload(),
    )
    created_category = create_session.add.call_args_list[0].args[0]
    assert created_category.img == image_url
    assert upload_image.await_args.kwargs["folder"] == "bestreserv/categories"

    old_image_url = "https://res.cloudinary.com/demo/image/upload/bestreserv/categories/old.jpg"
    category = Category(name="Hébergement", img=old_image_url)
    update_session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: category)
            )
        ),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    updated_category = await service.update(
        category.id,
        CategoryPatch(name="Hébergement modifié"),
        actor,
        request,
        update_session,
        image=_image_upload(),
    )

    assert updated_category.img == image_url
    destroy_image.assert_awaited_once_with(
        "bestreserv/categories/old",
        expected_folder="bestreserv/categories",
    )


@pytest.mark.anyio
async def test_category_update_without_image_upload_preserves_existing_image():
    image_url = "https://res.cloudinary.com/demo/image/upload/bestreserv/categories/stay.jpg"
    category = Category(name="Hébergement", img=image_url)
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: category)
            )
        ),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    updated = await CategoryService().update(
        category.id,
        CategoryPatch(name="Hébergements"),
        SimpleNamespace(id=uuid4()),
        SimpleNamespace(client=None, headers={}),
        session,
    )

    assert updated.name == "Hébergements"
    assert updated.img == image_url


@pytest.mark.anyio
async def test_category_update_requires_a_field_or_image():
    category = Category(name="Hébergement")
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: category)
            )
        ),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    with pytest.raises(HTTPException) as error:
        await CategoryService().update(
            category.id,
            CategoryPatch(),
            SimpleNamespace(id=uuid4()),
            SimpleNamespace(client=None, headers={}),
            session,
        )

    assert error.value.status_code == 422
    session.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_category_image_can_be_removed(monkeypatch):
    image_url = "https://res.cloudinary.com/demo/image/upload/bestreserv/categories/stay.jpg"
    category = Category(name="Hébergement", img=image_url)
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: category)
            )
        ),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    destroy_image = AsyncMock()
    monkeypatch.setattr("app.services.category.destroy_image", destroy_image)

    result = await CategoryService().delete_image(
        category.id,
        SimpleNamespace(id=uuid4()),
        SimpleNamespace(client=None, headers={}),
        session,
    )

    assert result.img is None
    destroy_image.assert_awaited_once_with(
        "bestreserv/categories/stay",
        expected_folder="bestreserv/categories",
    )
