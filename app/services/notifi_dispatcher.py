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


def notify_owner_application_received(
    *,
    recipient: str,
    name: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="owner_application_received",
        sender=email_service.send_owner_application_received_email,
        name=name,
    )


def notify_admin_owner_application_submitted(
    *,
    recipient: str,
    owner_name: str,
    owner_email: str,
    application_id: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="owner_application_submitted_admin",
        sender=email_service.send_owner_application_submitted_admin_email,
        owner_name=owner_name,
        owner_email=owner_email,
        application_id=application_id,
    )


def notify_owner_application_reviewed(
    *,
    recipient: str,
    name: str,
    approved: bool,
    rejection_reason: str | None = None,
) -> bool:
    if approved:
        return dispatch_email(
            recipient=recipient,
            event_name="owner_application_approved",
            sender=email_service.send_owner_application_approved_email,
            name=name,
        )

    return dispatch_email(
        recipient=recipient,
        event_name="owner_application_rejected",
        sender=email_service.send_owner_application_rejected_email,
        name=name,
        rejection_reason=rejection_reason or "Aucun motif communiqué.",
    )


def notify_reservation_refused(
    *,
    recipient: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
    refusal_reason: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="reservation_refused",
        sender=email_service.send_reservation_refused_email,
        name=name,
        reservation_reference=reservation_reference,
        establishment_name=establishment_name,
        refusal_reason=refusal_reason,
    )


def notify_reservation_completed(
    *,
    recipient: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="reservation_completed",
        sender=email_service.send_reservation_completed_email,
        name=name,
        reservation_reference=reservation_reference,
        establishment_name=establishment_name,
    )


def notify_location_access_payment(
    *,
    recipient: str,
    name: str,
    amount: str,
    transaction_reference: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="location_access_payment_success",
        sender=email_service.send_location_access_payment_email,
        name=name,
        amount=amount,
        transaction_reference=transaction_reference,
    )


def notify_otp(
    *,
    recipient: str,
    otp: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="account_otp",
        sender=email_service.send_otp_email,
        otp=otp,
    )


def notify_account_confirmed(
    *,
    recipient: str,
    name: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="account_confirmed",
        sender=email_service.send_confirmation_email,
        name=name,
    )


def notify_password_reset_requested(
    *,
    recipient: str,
    token: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="password_reset_requested",
        sender=email_service.send_reset_password_email,
        token=token,
    )


def notify_password_changed(
    *,
    recipient: str,
) -> bool:
    return dispatch_email(
        recipient=recipient,
        event_name="password_changed",
        sender=email_service.send_password_changed_email,
    )