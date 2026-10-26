# app/services/notification_dispatcher.py

import logging
from collections.abc import Callable
from typing import Any

from app.emails import email as email_service


logger = logging.getLogger(__name__)


def dispatch_email(
    *,
    recipient: str,
    event_name: str,
    sender: Callable[..., Any],
    **kwargs: Any,
) -> bool:
    """
    Envoie un email transactionnel.

    À appeler après le commit de l'opération métier.
    Un échec d'email ne doit pas annuler cette opération.
    """

    try:
        sender(email=recipient, **kwargs)

        logger.info(
            "Email transactionnel envoyé : event=%s",
            event_name,
        )

        return True

    except Exception:
        logger.exception(
            "Échec de l'email transactionnel : event=%s",
            event_name,
        )

        return False


def notify_reservation_created(
    *,
    recipient: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
    start_date: str,
    end_date: str,
    amount: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="reservation_created",
        sender=email_service.send_reservation_created_email,
        name=name,
        reservation_reference=reservation_reference,
        establishment_name=establishment_name,
        start_date=start_date,
        end_date=end_date,
        amount=amount,
    )


def notify_reservation_confirmed(
    *,
    recipient: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
    start_date: str,
    end_date: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="reservation_confirmed",
        sender=email_service.send_reservation_confirmed_email,
        name=name,
        reservation_reference=reservation_reference,
        establishment_name=establishment_name,
        start_date=start_date,
        end_date=end_date,
    )


def notify_reservation_cancelled(
    *,
    recipient: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
    cancellation_reason: str | None = None,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="reservation_cancelled",
        sender=email_service.send_reservation_cancelled_email,
        name=name,
        reservation_reference=reservation_reference,
        establishment_name=establishment_name,
        cancellation_reason=cancellation_reason,
    )


def notify_payment_success(
    *,
    recipient: str,
    name: str,
    reservation_reference: str,
    amount: str,
    transaction_reference: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="payment_success",
        sender=email_service.send_payment_success_email,
        name=name,
        reservation_reference=reservation_reference,
        amount=amount,
        transaction_reference=transaction_reference,
    )


def notify_refund(
    *,
    recipient: str,
    name: str,
    reservation_reference: str,
    amount: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="refund_completed",
        sender=email_service.send_refund_email,
        name=name,
        reservation_reference=reservation_reference,
        amount=amount,
    )