from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.api.admin import admin_users
from app.models.enums import EstablishmentStatus, UserRole, UserStatus
from app.schemas.admin_user import AdminUserAdminPublic, AdminUserCreate
from app.services.user import UserService
from app.utils import verify_password


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _Session:
    def __init__(self, results):
        self.results = iter(results)
        self.added = []

    async def execute(self, _statement):
        return next(self.results)

    def add(self, instance):
        self.added.append(instance)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, _instance, _attributes=None):
        pass


@pytest.mark.anyio
async def test_admin_user_response_lists_owner_properties_and_client_owners():
    owner_id = uuid4()
    client_id = uuid4()
    owner = SimpleNamespace(
        id=owner_id,
        email="owner@example.com",
        role=UserRole.PROPRIETAIRE,
        status=UserStatus.ACTIF,
        provider="LOCAL",
        profile=None,
    )
    client = SimpleNamespace(
        id=client_id,
        email="client@example.com",
        role=UserRole.CLIENT,
        status=UserStatus.ACTIF,
        provider="LOCAL",
        profile=None,
    )
    establishment = SimpleNamespace(
        owner_id=owner_id,
        id=uuid4(),
        name="Maison",
        slug="maison",
        status=EstablishmentStatus.PUBLIE,
    )
    session = _Session(
        [
            _Result([establishment]),
            _Result(
                [
                    (
                        client_id,
                        owner_id,
                        owner.email,
                        "Awa",
                        "Diallo",
                    )
                ]
            ),
        ]
    )

    summaries = await UserService()._serialize_admin_users(
        [owner, client],
        session,
    )
    owner_response, client_response = [
        AdminUserAdminPublic.model_validate(summary)
        for summary in summaries
    ]

    assert owner_response.establishments[0].id == establishment.id
    assert owner_response.establishments[0].status == EstablishmentStatus.PUBLIE
    assert client_response.owners[0].id == owner_id
    assert client_response.owners[0].firstName == "Awa"


@pytest.mark.anyio
async def test_admin_partner_mutations_reject_non_owner_accounts(monkeypatch):
    client = SimpleNamespace(role=UserRole.CLIENT)

    async def get_user(_user_id, _session):
        return client

    monkeypatch.setattr(admin_users, "_get_active_user", get_user)

    with pytest.raises(HTTPException) as error:
        await admin_users._get_active_partner(uuid4(), object())

    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_admin_create_creates_unverified_partner_and_sends_otp(monkeypatch):
    session = _Session([_Result([])])
    actor = SimpleNamespace(id=uuid4())
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "test"},
    )
    save_otp = AsyncMock()
    send_email = Mock()
    monkeypatch.setattr(admin_users, "save_otp", save_otp)
    monkeypatch.setattr(admin_users, "send_otp_email", send_email)

    result = await admin_users.create_user(
        AdminUserCreate(
            email="partner@example.com",
            password="SecurePass1!",
            firstName="Amie",
            lastName="Partenaire",
        ),
        request,
        actor,
        session,
    )

    assert result.role == UserRole.PROPRIETAIRE
    assert result.status == UserStatus.ACTIF
    assert result.email_verified is False
    assert result.created_by == actor.id
    assert verify_password("SecurePass1!", result.password)
    assert save_otp.await_count == 1
    assert send_email.call_count == 1
    assert send_email.call_args.args[0] == "partner@example.com"
