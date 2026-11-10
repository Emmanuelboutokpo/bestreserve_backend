from io import BytesIO
from urllib.parse import urlsplit
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.helpers.cloudinary import owner_document_download_url
from app.models import OwnerApplication, Profile, User
from app.models.enums import OwnerApplicationStatus, UserRole
from app.schemas.owners import OwnerApplicationDecision
from app.services.owners import OwnerApplicationService


MAX_DOCUMENT_SIZE = OwnerApplicationService.MAX_DOCUMENT_SIZE


class _Scalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value

    def one(self):
        return self.value


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalars(self):
        return _Scalars(self.value)

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, results):
        self.results = iter(results)
        self.added = []

    async def execute(self, _statement):
        return next(self.results)

    def add(self, instance):
        self.added.append(instance)

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, _instance):
        pass


def _application(owner, status):
    return OwnerApplication(
        owner_id=owner.id,
        owner=owner,
        status=status,
        registry_file_name="registry.pdf",
        registry_file_public_id="owner-documents/registry",
        registry_mime_type="application/pdf",
        registry_file_size=100,
        partnership_file_name="contract.pdf",
        partnership_file_public_id="owner-documents/contract",
        partnership_mime_type="application/pdf",
        partnership_file_size=100,
    )


def _upload(filename: str, content_type: str, contents: bytes) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(contents),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.anyio
async def test_read_document_accepts_matching_pdf():
    contents = b"%PDF-1.7\nexample"
    result = await OwnerApplicationService._read_document(
        _upload("registre.pdf", "application/pdf", contents)
    )

    assert result == (contents, "registre.pdf", "application/pdf")


@pytest.mark.anyio
async def test_read_document_accepts_file_at_size_limit():
    contents = b"%PDF-" + b"x" * (MAX_DOCUMENT_SIZE - 5)
    result = await OwnerApplicationService._read_document(
        _upload("registre.pdf", "application/pdf", contents)
    )

    assert len(result[0]) == MAX_DOCUMENT_SIZE


@pytest.mark.anyio
async def test_read_document_rejects_mismatched_content():
    with pytest.raises(HTTPException) as error:
        await OwnerApplicationService._read_document(
            _upload("registre.pdf", "application/pdf", b"not a pdf")
        )

    assert error.value.status_code == 422


@pytest.mark.anyio
async def test_read_document_rejects_files_over_limit():
    contents = b"%PDF-" + b"x" * MAX_DOCUMENT_SIZE

    with pytest.raises(HTTPException) as error:
        await OwnerApplicationService._read_document(
            _upload("registre.pdf", "application/pdf", contents)
        )

    assert error.value.status_code == 413


def test_rejection_requires_a_reason():
    with pytest.raises(ValueError):
        OwnerApplicationDecision(decision="REJETE")

    decision = OwnerApplicationDecision(
        decision="REJETE",
        rejection_reason="Documents illisibles",
    )
    assert decision.rejection_reason == "Documents illisibles"


def test_document_download_uses_a_signed_cloudinary_endpoint():
    url = owner_document_download_url(
        "bestreserv/owner-documents/test-id",
        "registre.pdf",
    )
    parsed_url = urlsplit(url)

    assert parsed_url.scheme == "https"
    assert parsed_url.path.endswith("/raw/download")
    assert "signature=" in parsed_url.query


def test_application_review_timestamps_are_timezone_aware():
    assert OwnerApplication.__table__.c.submitted_at.type.timezone is True
    assert OwnerApplication.__table__.c.reviewed_at.type.timezone is True


def test_application_response_includes_owner_profile_details():
    owner = User(
        email="owner@example.com",
        role=UserRole.PROPRIETAIRE,
    )
    owner.profile = Profile(
        user_id=owner.id,
        firstName="Ada",
        lastName="Lovelace",
        phone="+123456789",
        city="Lagos",
    )
    application = OwnerApplication(
        owner_id=owner.id,
        owner=owner,
        status=OwnerApplicationStatus.EN_ATTENTE,
        registry_file_name="registry.pdf",
        registry_file_public_id="owner-documents/registry",
        registry_mime_type="application/pdf",
        registry_file_size=100,
        partnership_file_name="contract.pdf",
        partnership_file_public_id="owner-documents/contract",
        partnership_mime_type="application/pdf",
        partnership_file_size=100,
    )

    response = OwnerApplicationService._to_public(application)

    assert response.owner.email == "owner@example.com"
    assert response.owner.firstName == "Ada"
    assert response.owner.lastName == "Lovelace"
    assert response.owner.phone == "+123456789"
    assert response.owner.city == "Lagos"


@pytest.mark.anyio
async def test_rejected_application_can_be_resubmitted_with_corrected_documents(
    monkeypatch,
):
    owner = User(
        id=uuid4(),
        email="owner@example.com",
        role=UserRole.PROPRIETAIRE,
    )
    owner.profile = Profile(user_id=owner.id)
    rejected_application = _application(
        owner,
        OwnerApplicationStatus.REJETE,
    )
    session = _Session(
        [
            _Result(rejected_application),
            _Result(),
            _Result(rejected_application),
        ]
    )
    service = OwnerApplicationService()
    service._read_document = AsyncMock(
        side_effect=[
            (b"%PDF-registry", "registry.pdf", "application/pdf"),
            (b"%PDF-contract", "contract.pdf", "application/pdf"),
        ]
    )
    monkeypatch.setattr(
        "app.services.owners.upload_owner_document",
        AsyncMock(
            side_effect=[
                {"public_id": "owner-documents/new-registry"},
                {"public_id": "owner-documents/new-contract"},
            ]
        ),
    )
    monkeypatch.setattr(
        "app.services.owners.owner_document_download_url",
        lambda public_id, filename: f"https://files.example/{public_id}/{filename}",
    )

    original_execute = session.execute
    execute_count = 0

    async def tracked_execute(statement):
        nonlocal execute_count
        execute_count += 1
        if session.added and execute_count == 4:
            session.added[0].owner = owner
            return _Result(session.added[0])
        return await original_execute(statement)

    session.execute = tracked_execute
    result = await service.submit(
        owner,
        _upload("registry.pdf", "application/pdf", b"%PDF-registry"),
        _upload("contract.pdf", "application/pdf", b"%PDF-contract"),
        session,
    )

    assert result.id != rejected_application.id
    assert result.status == OwnerApplicationStatus.EN_ATTENTE
    assert rejected_application.status == OwnerApplicationStatus.REJETE
    assert result.registry_document_url.endswith(
        "owner-documents/new-registry/registry.pdf"
    )


@pytest.mark.anyio
async def test_admin_can_approve_pending_resubmission(monkeypatch):
    owner = User(
        id=uuid4(),
        email="owner@example.com",
        role=UserRole.PROPRIETAIRE,
    )
    owner.profile = Profile(user_id=owner.id)
    rejected_application = _application(
        owner,
        OwnerApplicationStatus.REJETE,
    )
    corrected_application = _application(
        owner,
        OwnerApplicationStatus.EN_ATTENTE,
    )
    reviewer = User(
        id=uuid4(),
        email="admin@example.com",
        role=UserRole.ADMIN,
    )
    session = _Session([_Result(corrected_application)])
    monkeypatch.setattr(
        "app.services.owners.owner_document_download_url",
        lambda public_id, filename: f"https://files.example/{public_id}/{filename}",
    )

    result = await OwnerApplicationService().review(
        corrected_application.id,
        OwnerApplicationDecision(decision="APPROUVE"),
        reviewer,
        session,
    )

    assert result.status == OwnerApplicationStatus.APPROUVE
    assert corrected_application.reviewed_by == reviewer.id
    assert corrected_application.reviewed_at is not None
    assert corrected_application.rejection_reason is None
    assert rejected_application.status == OwnerApplicationStatus.REJETE

    approval_session = _Session([_Result(corrected_application.id)])
    assert await OwnerApplicationService().is_approved(
        owner.id,
        approval_session,
    )
