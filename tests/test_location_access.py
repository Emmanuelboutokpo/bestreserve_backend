from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AvailabilityStatus, PaymentMethod, PaymentStatus
from app.models.enums import ReservationStatus
from app.api.reservations import _client_reservation_response
from app.main import app
from app.services.establishment import establishment_service
from app.services.favorite import FavoriteService
from app.services.location_access import (
    LOCATION_ACCESS_AMOUNT,
    confirm_location_access_payment,
    create_location_access_payment,
)


def _mapped(**values):
    return SimpleNamespace(
        **values,
        __mapper__=SimpleNamespace(
            column_attrs=[
                SimpleNamespace(key=key)
                for key in values
            ]
        ),
    )


def _establishment(category_name: str):
    location = _mapped(
        id=uuid4(),
        name="Cotonou",
        type="CITY",
        latitude=6.37,
        longitude=2.43,
        country_code="BJ",
        metadata_json='{"district": "Akpakpa"}',
    )
    category = _mapped(id=uuid4(), name=category_name)
    establishment = SimpleNamespace(
        id=uuid4(),
        category_id=category.id,
        subcategory_id=None,
        location_id=location.id,
        name="Établissement de test",
        slug="etablissement-test",
        description="Description publique",
        address="Rue précise, Akpakpa",
        latitude=Decimal("6.3700000"),
        longitude=Decimal("2.4300000"),
        category=category,
        subcategory=None,
        location=location,
        amenity_links=[],
        photos=[],
        rating=Decimal("4.5"),
        reviews_count=2,
        price=Decimal("1000"),
        price_per_night=None,
        price_per_month=None,
        price_unit=None,
        currency="XOF",
        capacity=None,
        rooms_count=None,
        cuisine_type=None,
        opening_hours=None,
        area=None,
        availability_status=AvailabilityStatus.AVAILABLE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        payment_condition_links=[],
        owner=None,
    )
    establishment.__mapper__ = SimpleNamespace(
        column_attrs=[
            SimpleNamespace(key=key)
            for key in (
                "id",
                "category_id",
                "subcategory_id",
                "location_id",
                "name",
                "slug",
                "description",
                "address",
                "latitude",
                "longitude",
                "price",
                "price_per_night",
                "price_per_month",
                "price_unit",
                "currency",
                "capacity",
                "rooms_count",
                "cuisine_type",
                "opening_hours",
                "area",
                "availability_status",
                "rating",
                "reviews_count",
                "created_at",
                "updated_at",
            )
        ]
    )
    return establishment


def _query_result(value=None):
    return SimpleNamespace(
        scalars=lambda: SimpleNamespace(first=lambda: value),
        first=lambda: value,
        scalar_one_or_none=lambda: value,
    )


def test_unpaid_public_establishment_hides_precise_location_only():
    establishment = _establishment("Restaurant")

    list_item = establishment_service.serialize_list_item(establishment)
    detail = establishment_service.serialize_detail(establishment)

    for serialized in (list_item, detail):
        assert serialized["address"] is None
        assert serialized["latitude"] is None
        assert serialized["longitude"] is None
        assert serialized["location"] == {
            "id": establishment.location.id,
            "name": "Cotonou",
            "type": "CITY",
        }
        assert serialized["name"] == establishment.name
        assert serialized["description"] == establishment.description


def test_paid_and_lodging_establishments_keep_location_data():
    restaurant = _establishment("Restaurant")
    lodging = _establishment("Hébergement")

    paid_detail = establishment_service.serialize_detail(
        restaurant,
        location_access=True,
    )
    lodging_detail = establishment_service.serialize_detail(lodging)

    assert paid_detail["address"] == restaurant.address
    assert paid_detail["latitude"] == restaurant.latitude
    assert paid_detail["longitude"] == restaurant.longitude
    assert paid_detail["location"]["latitude"] == 6.37
    assert lodging_detail["address"] == lodging.address
    assert lodging_detail["latitude"] == lodging.latitude


@pytest.mark.anyio
async def test_favorites_hide_precise_location_before_purchase():
    establishment = _establishment("Restaurant")
    favorite = SimpleNamespace(
        id=uuid4(),
        establishment_id=establishment.id,
        note=None,
        created_at=datetime.now(timezone.utc),
        establishment=establishment,
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one=lambda: 1),
                SimpleNamespace(
                    scalars=lambda: SimpleNamespace(all=lambda: [favorite])
                ),
            ]
        )
    )

    response = await FavoriteService.list_my_favorites(
        user_id=uuid4(),
        session=cast(AsyncSession, session),
        limit=20,
        offset=0,
        location_access=False,
    )

    assert response["items"][0]["establishment"]["address"] is None
    assert response["items"][0]["establishment"]["latitude"] is None
    assert response["items"][0]["establishment"]["longitude"] is None


def test_client_reservation_hides_restaurant_address_until_access():
    now = datetime.now(timezone.utc)
    establishment_id = uuid4()
    reservation = SimpleNamespace(
        id=uuid4(),
        reference="BR-TEST12345",
        establishment_id=establishment_id,
        establishment=SimpleNamespace(
            id=establishment_id,
            name="Restaurant",
            slug="restaurant",
            address="Adresse précise",
        ),
        category="Restaurant",
        reservation_date=None,
        start_date=None,
        end_date=None,
        start_time=None,
        end_time=None,
        quantity=1,
        nights=None,
        adults=1,
        children=0,
        room_or_unit=None,
        options={},
        special_requests=None,
        subtotal=Decimal("500"),
        service_fee=Decimal("0"),
        total=Decimal("500"),
        currency="XOF",
        payment_method=None,
        payment_status=PaymentStatus.EN_ATTENTE,
        status=ReservationStatus.EN_ATTENTE,
        cancelled_at=None,
        cancellation_reason=None,
        created_at=now,
        updated_at=now,
    )

    response = _client_reservation_response(
        reservation,
        location_access=False,
    )

    assert response.establishment is not None
    assert response.establishment.address is None


def test_location_access_routes_are_exposed():
    paths = app.openapi()["paths"]

    assert set(paths["/api/v1/payments/location-access/checkout"]) == {
        "post"
    }
    assert set(paths["/api/v1/payments/location-access/confirm"]) == {
        "post"
    }
    assert set(paths["/api/v1/payments/location-access"]) == {"get"}


@pytest.mark.anyio
async def test_location_access_checkout_uses_fixed_amount_and_kkiapay():
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _query_result(),
                _query_result(),
                _query_result(),
                _query_result(),
            ]
        ),
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )
    settings_patch = {
        "kkiapay_public_key": "public",
        "kkiapay_private_key": "private",
        "kkiapay_secret_key": "secret",
        "kkiapay_sandbox": True,
    }

    with patch.multiple("app.services.location_access.settings", **settings_patch):
        response = await create_location_access_payment(
            user_id=uuid4(),
            payment_method=PaymentMethod.MOBILE_MONEY,
            idempotency_key="location-access-key-123",
            session=session,
        )

    payment = session.add.call_args.args[0]
    assert payment.amount == LOCATION_ACCESS_AMOUNT
    assert payment.status == PaymentStatus.EN_ATTENTE
    assert response["amount"] == 500
    assert response["currency"] == "XOF"
    assert response["requires_widget"] is True
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_location_access_requires_verified_exact_amount():
    payment = SimpleNamespace(
        id=uuid4(),
        transaction_ref="TX-LOCATION123",
        user_id=uuid4(),
        provider="KKIAPAY",
        provider_transaction_id=None,
        amount=Decimal("500.00"),
        currency="XOF",
        status=PaymentStatus.EN_ATTENTE,
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _query_result(payment),
                _query_result(),
                _query_result(),
            ]
        ),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )

    with patch(
        "app.services.location_access.verify_remote_transaction",
        new=AsyncMock(
            return_value={
                "transactionId": "kkiapay-transaction-1",
                "status": "SUCCESS",
                "amount": 499,
            }
        ),
    ):
        with pytest.raises(HTTPException) as error:
            await confirm_location_access_payment(
                transaction_ref=payment.transaction_ref,
                provider_transaction_id="kkiapay-transaction-1",
                user_id=payment.user_id,
                session=session,
            )

    assert error.value.status_code == 409
    assert payment.status == PaymentStatus.EN_ATTENTE
    session.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_location_access_is_granted_only_after_kkiapay_success():
    payment = SimpleNamespace(
        id=uuid4(),
        transaction_ref="TX-LOCATION123",
        user_id=uuid4(),
        provider="KKIAPAY",
        provider_transaction_id=None,
        amount=Decimal("500.00"),
        currency="XOF",
        status=PaymentStatus.EN_ATTENTE,
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _query_result(payment),
                _query_result(),
                _query_result(),
                _query_result(
                    SimpleNamespace(
                        id=payment.user_id,
                        email="client@example.com",
                        profile=SimpleNamespace(
                            firstName="Client",
                            lastName="BestRev",
                        ),
                    )
                ),
            ]
        ),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )

    with (
        patch(
            "app.services.location_access.verify_remote_transaction",
            new=AsyncMock(
                return_value={
                    "transactionId": "kkiapay-transaction-2",
                    "status": "SUCCESS",
                    "amount": 500,
                }
            ),
        ),
        patch(
            "app.services.location_access.notify_location_access_payment"
        ) as notify,
    ):
        confirmed = await confirm_location_access_payment(
            transaction_ref=payment.transaction_ref,
            provider_transaction_id="kkiapay-transaction-2",
            user_id=payment.user_id,
            session=session,
        )

    assert confirmed.status == PaymentStatus.PAYE
    assert confirmed.provider_transaction_id == "kkiapay-transaction-2"
    session.commit.assert_awaited_once()
    notify.assert_called_once_with(
        recipient="client@example.com",
        name="Client BestRev",
        amount="500.00 XOF",
        transaction_reference="kkiapay-transaction-2",
    )


def test_email_template_uses_green_for_important_content_and_escapes_text():
    from app.emails import email as email_service

    with patch.object(
        email_service,
        "send_email",
        return_value={"id": "email-id"},
    ) as send:
        result = email_service.send_owner_application_rejected_email(
            email="owner@example.com",
            name="<Owner>",
            rejection_reason="<script>alert(1)</script>",
        )

    assert result == {"id": "email-id"}
    body = send.call_args.kwargs["html_body"]
    assert "#218c5a" in body
    assert "#176b45" in body
    assert "&lt;Owner&gt;" in body
    assert "&lt;script&gt;" in body
    assert "<script>" not in body
