from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.establishment import establishment_service


@pytest.mark.anyio
async def test_owner_establishment_route_passes_authenticated_owner_to_shared_service():
    from app.api.owners.establishments import list_my_establishments

    owner = SimpleNamespace(id=uuid4())
    session = SimpleNamespace()
    expected_page = {"items": [], "total": 0, "limit": 20, "offset": 0}
    service = AsyncMock(return_value=expected_page)

    with patch.object(
        establishment_service,
        "list_admin_establishments",
        new=service,
    ):
        result = await list_my_establishments(actor=owner, db=session)

    assert result == expected_page
    service.assert_awaited_once()
    assert service.await_args.kwargs["owner_id"] == owner.id


@pytest.mark.anyio
async def test_establishment_list_filters_by_owner():
    owner_id = uuid4()
    count_result = SimpleNamespace(scalar_one=lambda: 0)
    list_result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(
            unique=lambda: SimpleNamespace(all=lambda: [])
        )
    )
    session = SimpleNamespace(
        execute=AsyncMock(side_effect=[count_result, list_result])
    )

    await establishment_service.list_admin_establishments(
        session,
        owner_id=owner_id,
    )

    assert session.execute.await_count == 2
    for call in session.execute.await_args_list:
        statement = call.args[0]
        assert "establishments.owner_id" in str(statement)
        assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_establishment_detail_is_scoped_to_owner():
    owner_id = uuid4()
    establishment_id = uuid4()
    result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(
            unique=lambda: SimpleNamespace(first=lambda: None)
        )
    )
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as error:
        await establishment_service._get_admin_establishment(
            establishment_id,
            session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404
