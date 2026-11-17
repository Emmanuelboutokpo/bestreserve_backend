from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.owners import establishments as owner_establishments
from app.models.enums import EstablishmentStatus
from app.schemas.establishment import (
    EstablishmentPatch,
    EstablishmentStatusPatch,
)
from app.services.owner_scope import (
    category_type_for_name,
    is_owner_managed_category_name,
    owner_establishment_ids,
    validate_owner_category,
)


@pytest.mark.parametrize(
    "name",
    [
        "Hébergement",
        "Hébergements",
        "Hôtel",
        "Logement",
        "Accommodation",
    ],
)
def test_only_lodging_categories_are_owner_managed(name):
    assert is_owner_managed_category_name(name)


@pytest.mark.parametrize("name", ["Restaurant", "Loisirs", "Activités"])
def test_restaurants_and_leisure_are_not_owner_managed(name):
    assert not is_owner_managed_category_name(name)


@pytest.mark.parametrize(
    ("name", "category_type"),
    [
        ("Restaurant", "restaurant"),
        ("Restauration", "restaurant"),
        ("Loisirs", "loisir"),
        ("Activités", "loisir"),
        ("Expérience", "loisir"),
        ("Hôtel", "hebergement"),
        ("Services", None),
    ],
)
def test_category_type_for_managed_establishment_names(name, category_type):
    assert category_type_for_name(name) == category_type


@pytest.mark.anyio
async def test_non_lodging_category_is_forbidden_to_owners():
    result = SimpleNamespace(scalar_one_or_none=lambda: "Restaurant")
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as error:
        await validate_owner_category(uuid4(), session)

    assert error.value.status_code == 403


def test_owner_establishment_scope_filters_to_lodging_category():
    owner_id = uuid4()
    statement = owner_establishment_ids(owner_id)
    compiled = statement.compile()

    assert "establishments.owner_id" in str(statement)
    assert "categories.name" in str(statement)
    assert owner_id in compiled.params.values()


@pytest.mark.anyio
async def test_owner_cannot_create_non_lodging_establishment():
    category_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    service = owner_establishments.establishment_service
    validator = AsyncMock(
        side_effect=HTTPException(
            status_code=403,
            detail="Les propriétaires peuvent gérer uniquement les hébergements.",
        )
    )

    with (
        patch.object(
            service,
            "_validate_owner_category",
            new=validator,
        ),
        patch.object(
            service,
            "_validate_references",
            new=AsyncMock(),
        ) as validate_references,
    ):
        with pytest.raises(HTTPException) as error:
            await owner_establishments.create_establishment(
                data=SimpleNamespace(
                    category_id=category_id,
                    subcategory_id=None,
                ),
                request=SimpleNamespace(),
                actor=actor,
                db=SimpleNamespace(),
            )

    assert error.value.status_code == 403
    validate_references.assert_not_awaited()


@pytest.mark.anyio
async def test_owner_cannot_reclassify_establishment_as_non_lodging():
    establishment = SimpleNamespace(
        id=uuid4(),
        category_id=uuid4(),
        subcategory_id=None,
        location_id=uuid4(),
    )
    validator = AsyncMock(
        side_effect=HTTPException(status_code=403, detail="forbidden")
    )
    service = owner_establishments.establishment_service

    with (
        patch.object(
            service,
            "_get_admin_establishment",
            new=AsyncMock(return_value=establishment),
        ),
        patch.object(service, "_validate_owner_category", new=validator),
    ):
        with pytest.raises(HTTPException) as error:
            await owner_establishments.update_establishment(
                establishment_id=establishment.id,
                data=EstablishmentPatch(category_id=uuid4()),
                request=SimpleNamespace(),
                actor=SimpleNamespace(id=uuid4()),
                db=SimpleNamespace(),
            )

    assert error.value.status_code == 403
    validator.assert_awaited_once()


@pytest.mark.anyio
async def test_owner_cannot_publish_non_lodging_establishment():
    establishment = SimpleNamespace(
        id=uuid4(),
        category_id=uuid4(),
        subcategory_id=None,
        location_id=uuid4(),
    )
    validator = AsyncMock(
        side_effect=HTTPException(status_code=403, detail="forbidden")
    )
    service = owner_establishments.establishment_service
    session = SimpleNamespace()

    with (
        patch.object(
            service,
            "_get_admin_establishment",
            new=AsyncMock(return_value=establishment),
        ),
        patch.object(service, "_validate_owner_category", new=validator),
    ):
        with pytest.raises(HTTPException) as error:
            await owner_establishments.update_establishment_status(
                establishment_id=establishment.id,
                data=EstablishmentStatusPatch(status=EstablishmentStatus.PUBLIE),
                request=SimpleNamespace(),
                actor=SimpleNamespace(id=uuid4()),
                db=session,
            )

    assert error.value.status_code == 403
    validator.assert_awaited_once_with(establishment.category_id, session)
