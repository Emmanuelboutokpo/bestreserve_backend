from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import reservation as reservation_service
from app.services import stats as stats_service
from app.services import payment as payment_service
from app.services import payment_condition as payment_condition_service
from app.services import reviews as review_service
from app.services.amenity import AmenityService
from app.services.account import AccountService
from app.services.establishment import EstablishmentService
from app.services.notification import create_admin_notification
from app.services.user import UserService
from app.schemas.account import AccountProfilePatch
from app.schemas.payment_condition import PaymentConditionCreate
from app.services.payment import _checkout_amount
from app.services.reservation import _find_idempotent
from app.models.enums import (
    PaymentConditionType,
    PaymentMethod,
    PaymentStatus,
    ReservationStatus,
)
from app.services.reservation import _reservation_values
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationPublic


def _session(**members: object) -> AsyncSession:
    return cast(AsyncSession, SimpleNamespace(**members))


@pytest.mark.anyio
async def test_owner_reservation_list_filters_count_and_rows_by_owner():
    owner_id = uuid4()
    session = _session(
        scalar=AsyncMock(return_value=0),
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [])
            )
        ),
    )

    await reservation_service.list_admin_reservations(
        session,
        page=1,
        page_size=20,
        status_filter=None,
        status=None,
        establishment_id=None,
        user_id=None,
        start_date=None,
        end_date=None,
        search=None,
        owner_id=owner_id,
    )

    statements = [
        session.scalar.await_args.args[0],
        session.execute.await_args.args[0],
    ]
    for statement in statements:
        assert "establishments.owner_id" in str(statement)
        assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_owner_reservation_detail_hides_other_owners_reservations():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: None)
            )
        )
    )

    with pytest.raises(HTTPException) as error:
        await reservation_service.get_admin_reservation(
            uuid4(),
            session,
            for_update=False,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_reservation_stats_filters_by_owner():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [])
            )
        )
    )

    await reservation_service.get_reservation_stats(
        session,
        start_date=None,
        end_date=None,
        owner_id=owner_id,
    )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_owner_user_list_only_includes_customers_with_owner_reservations():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one=lambda: 0),
                SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [])),
            ]
        )
    )

    await UserService().list_owner_users(owner_id, session)

    for call in session.execute.await_args_list:
        statement = call.args[0]
        assert "establishments.owner_id" in str(statement)
        assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_owner_user_stats_only_include_customers_with_owner_reservations():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                one=lambda: (0, 0, 0, 0, 0, 0, 0, 0)
            )
        )
    )

    await stats_service.get_stats_users(
        session,
        start_date=None,
        end_date=None,
        owner_id=owner_id,
    )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_owner_general_reservation_stats_are_scoped():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(one=lambda: (0, 0, 0, 0, 0, 0, 0))
        )
    )

    await stats_service.get_stats_reservations(
        session,
        start_date=None,
        end_date=None,
        owner_id=owner_id,
    )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_reservation_stats_without_owner_remain_global():
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [])
            )
        )
    )

    await reservation_service.get_reservation_stats(session)

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" not in str(statement)


@pytest.mark.anyio
async def test_general_reservation_stats_without_owner_remain_global():
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(one=lambda: (0, 0, 0, 0, 0, 0, 0))
        )
    )

    await stats_service.get_stats_reservations(session)

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" not in str(statement)


@pytest.mark.anyio
async def test_owner_payment_list_and_count_are_scoped():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one=lambda: 0),
                SimpleNamespace(all=lambda: []),
            ]
        )
    )

    await payment_service.list_admin_payments(
        session=session,
        owner_id=owner_id,
    )

    for call in session.execute.await_args_list:
        statement = call.args[0]
        assert "establishments.owner_id" in str(statement)
        assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_owner_payment_detail_hides_other_owners_transactions():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(first=lambda: None)
        )
    )

    with pytest.raises(HTTPException) as error:
        await payment_service.get_admin_payment(
            transaction_id=uuid4(),
            session=session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_payment_statistics_scope_payments_and_refunds():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(all=lambda: []),
                SimpleNamespace(all=lambda: []),
            ]
        )
    )

    await payment_service.get_admin_payment_stats(
        session=session,
        owner_id=owner_id,
    )

    assert session.execute.await_count == 2
    for call in session.execute.await_args_list:
        statement = call.args[0]
        assert "establishments.owner_id" in str(statement)
        assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_payment_list_without_owner_keeps_admin_scope_global():
    session = _session(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one=lambda: 0),
                SimpleNamespace(all=lambda: []),
            ]
        )
    )

    await payment_service.list_admin_payments(session=session)

    for call in session.execute.await_args_list:
        assert not any(
            isinstance(value, UUID)
            for value in call.args[0].compile().params.values()
        )


@pytest.mark.anyio
async def test_owner_review_list_and_count_are_scoped():
    owner_id = uuid4()
    session = _session(
        scalar=AsyncMock(return_value=0),
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [])
            )
        ),
    )

    await review_service.list_admin_reviews(
        limit=20,
        offset=0,
        approved=None,
        establishment_id=None,
        session=session,
        owner_id=owner_id,
    )

    for statement in (
        session.scalar.await_args.args[0],
        session.execute.await_args.args[0],
    ):
        assert "establishments.owner_id" in str(statement)
        assert owner_id in statement.compile().params.values()


@pytest.mark.anyio
async def test_owner_review_approval_cannot_load_another_owners_review():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: None)
            )
        )
    )

    with pytest.raises(HTTPException) as error:
        await review_service.approve_review(
            review_id=uuid4(),
            session=session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_amenity_changes_only_load_owned_establishments():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: None)
            )
        )
    )

    with pytest.raises(HTTPException) as error:
        await AmenityService.get_establishment(
            uuid4(),
            session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_media_detail_hides_photos_from_other_establishments():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: None)
            )
        )
    )

    with pytest.raises(HTTPException) as error:
        await EstablishmentService()._get_admin_photo(
            uuid4(),
            session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_account_operations_reject_unrelated_clients():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: None)
            )
        )
    )

    with pytest.raises(HTTPException) as error:
        await AccountService().admin_update_profile(
            user_id=uuid4(),
            data=AccountProfilePatch(firstName="Test"),
            session=session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_notification_rejects_recipients_outside_its_customers():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
        )
    )

    with pytest.raises(HTTPException) as error:
        await create_admin_notification(
            user_id=uuid4(),
            notification_type="SYSTEM",
            title="Info",
            message="Message",
            action_url=None,
            session=session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_cannot_read_other_establishments_payment_conditions():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: None)
            )
        )
    )

    with pytest.raises(HTTPException) as error:
        await payment_condition_service.get_establishment_payment_conditions(
            uuid4(),
            session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_owner_cannot_change_other_establishments_payment_conditions():
    owner_id = uuid4()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: None)
            )
        )
    )

    with pytest.raises(HTTPException) as error:
        await payment_condition_service.set_establishment_payment_conditions(
            uuid4(),
            [uuid4()],
            session,
            owner_id=owner_id,
        )

    statement = session.execute.await_args.args[0]
    assert "establishments.owner_id" in str(statement)
    assert owner_id in statement.compile().params.values()
    assert session.execute.await_count == 1
    assert error.value.status_code == 404


def test_full_payment_condition_charges_entire_remaining_balance():
    reservation = SimpleNamespace(
        pricing_snapshot={
            "payment_condition": {
                "condition_type": PaymentConditionType.PAIEMENT_INTEGRAL.value,
            }
        },
        payment_method=PaymentMethod.MOBILE_MONEY,
        balance_due=Decimal("1250"),
        amount_paid=Decimal("0"),
        total=Decimal("1250"),
    )

    assert _checkout_amount(reservation) == Decimal("1250")


def test_deposit_charges_percentage_once_then_remaining_balance():
    policy_snapshot = {
        "payment_condition": {
            "condition_type": PaymentConditionType.ACOMPTE.value,
            "percentage": 30,
        }
    }
    initial_reservation = SimpleNamespace(
        pricing_snapshot=policy_snapshot,
        payment_method=None,
        balance_due=Decimal("1000"),
        amount_paid=Decimal("0"),
        total=Decimal("1000"),
    )
    after_deposit_reservation = SimpleNamespace(
        pricing_snapshot=policy_snapshot,
        payment_method=None,
        balance_due=Decimal("700"),
        amount_paid=Decimal("300"),
        total=Decimal("1000"),
    )

    assert _checkout_amount(initial_reservation) == Decimal("300")
    assert _checkout_amount(after_deposit_reservation) == Decimal("700")


def test_on_site_condition_rejects_online_checkout():
    reservation = SimpleNamespace(
        pricing_snapshot={
            "payment_condition": {
                "condition_type": PaymentConditionType.SUR_PLACE.value,
            }
        },
        payment_method=PaymentMethod.SUR_PLACE,
        balance_due=Decimal("1000"),
        amount_paid=Decimal("0"),
        total=Decimal("1000"),
    )

    with pytest.raises(HTTPException) as error:
        _checkout_amount(reservation)

    assert error.value.status_code == 409


def test_deposit_without_percentage_is_rejected():
    reservation = SimpleNamespace(
        pricing_snapshot={
            "payment_condition": {
                "condition_type": PaymentConditionType.ACOMPTE.value,
            }
        },
        payment_method=None,
        balance_due=Decimal("1000"),
        amount_paid=Decimal("0"),
        total=Decimal("1000"),
    )

    with pytest.raises(HTTPException) as error:
        _checkout_amount(reservation)

    assert error.value.status_code == 409


@pytest.mark.anyio
async def test_payment_condition_service_rejects_deposit_without_percentage():
    session = _session(
        add=lambda item: None,
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    data = PaymentConditionCreate(
        name="Acompte",
        condition_type=PaymentConditionType.ACOMPTE,
    )

    with pytest.raises(HTTPException) as error:
        await payment_condition_service.create_payment_condition(
            data,
            session,
        )

    assert error.value.status_code == 422
    session.commit.assert_not_awaited()


def test_reservation_persists_selected_payment_condition_snapshot():
    user_id = uuid4()
    condition = {
        "id": str(uuid4()),
        "name": "Acompte 30%",
        "condition_type": PaymentConditionType.ACOMPTE.value,
        "percentage": 30,
    }
    data = SimpleNamespace(
        start_date=None,
        end_date=None,
        start_time=None,
        end_time=None,
        quantity=1,
        adults=1,
        children=0,
        room_or_unit=None,
        options=None,
        special_requests=None,
        payment_method=None,
    )
    user = SimpleNamespace(
        id=user_id,
        email="client@example.com",
        profile=None,
    )
    establishment = SimpleNamespace(
        id=uuid4(),
        name="Hôtel",
        category=None,
    )
    quote = {
        "total": Decimal("1000"),
        "subtotal": Decimal("1000"),
        "service_fee": Decimal("0"),
        "tax_amount": Decimal("0"),
        "discount_amount": Decimal("0"),
        "currency": "XOF",
        "selected_payment_condition": condition,
    }

    values = _reservation_values(
        data,
        user,
        establishment,
        quote,
        idempotency_key=None,
    )

    assert values["pricing_snapshot"]["payment_condition"] == condition
    assert values["balance_due"] == Decimal("1000")


def test_reservation_response_includes_selected_payment_condition():
    condition = {
        "id": str(uuid4()),
        "name": "Acompte 30%",
        "condition_type": PaymentConditionType.ACOMPTE.value,
        "percentage": 30,
    }
    reservation = Reservation(
        user_id=uuid4(),
        establishment_id=uuid4(),
        client_first_name="Client",
        client_last_name="Test",
        client_email="client@example.com",
        pricing_snapshot={"payment_condition": condition},
        quantity=1,
        adults=1,
        children=0,
        subtotal=Decimal("1000"),
        service_fee=Decimal("0"),
        total=Decimal("1000"),
        currency="XOF",
        payment_status=PaymentStatus.EN_ATTENTE,
        status=ReservationStatus.EN_ATTENTE,
    )

    response = ReservationPublic.model_validate(reservation)

    assert response.payment_condition == condition


@pytest.mark.anyio
async def test_idempotent_reservation_lookup_eager_loads_establishment():
    reservation = object()
    session = _session(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(first=lambda: reservation)
            )
        )
    )

    result = await _find_idempotent(
        session,
        user_id=uuid4(),
        key="request-key",
    )

    statement = session.execute.await_args.args[0]
    assert result is reservation
    assert any(
        "Reservation.establishment" in str(option.path)
        for option in statement._with_options
    )
