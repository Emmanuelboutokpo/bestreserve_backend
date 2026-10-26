import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_client
from app.models.enums import TransactionType
from app.models.reservation import Reservation
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.payments import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentConfirmRequest,
    PaymentPublic,
)
from app.services.payment import (
    confirm_payment,
    create_payment,
    verify_webhook_secret,
)

logger = logging.getLogger(__name__)

payments_router = APIRouter(
    prefix="/payments",
    tags=["Paiements KKiaPay"],
)

MAX_WEBHOOK_BODY_BYTES = 256 * 1024
PAYMENT_PROVIDER = "KKIAPAY"


def serialize_payment(transaction: Transaction, reservation: Reservation) -> dict[str, Any]:
    """Construit la réponse publique sans exposer les données internes."""
    return {
        "transaction_ref": transaction.transaction_ref,
        "reservation_reference": reservation.reference,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "status": transaction.status,
        "provider": transaction.provider,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
    }


@payments_router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout(
    data: CheckoutRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=255,
        description="Clé unique réutilisée pour chaque nouvelle tentative logique de paiement.",
    ),
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    """
    Initialise un paiement KKiaPay.

    Le client doit réutiliser la même Idempotency-Key lors d'une reprise
    de la même requête et générer une nouvelle clé pour une nouvelle tentative.
    """
    return await create_payment(
        reservation_id=data.reservation_id,
        user_id=current_user.id,
        payment_method=data.payment_method,
        idempotency_key=idempotency_key,
        session=session,
    )


@payments_router.post(
    "/confirm",
    response_model=PaymentPublic,
)
async def confirm_checkout(
    data: PaymentConfirmRequest,
    current_user: User = Depends(require_client),
    session: AsyncSession = Depends(get_session),
):
    """Vérifie auprès de KKiaPay la transaction communiquée par le client."""
    transaction = await confirm_payment(
        transaction_ref=data.transaction_ref,
        provider_transaction_id=data.provider_transaction_id,
        user_id=current_user.id,
        session=session,
    )

    result = await session.execute(
        select(Reservation).where(Reservation.id == transaction.reservation_id)
    )
    reservation = result.scalars().first()

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Réservation associée au paiement introuvable.",
        )

    return serialize_payment(transaction, reservation)


@payments_router.post(
    "/webhook/kkiapay",
    status_code=status.HTTP_200_OK,
)
async def kkiapay_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Reçoit une notification KKiaPay puis vérifie la transaction côté serveur.

    Le webhook n'est jamais utilisé seul comme preuve de paiement.
    """
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        if int(content_length) > MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Payload webhook trop volumineux.",
            )

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Payload webhook trop volumineux.",
            )

    received_secret = request.headers.get("x-kkiapay-secret")
    if not verify_webhook_secret(received_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Secret du webhook KKiaPay invalide.",
        )

    try:
        event = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload webhook invalide.",
        ) from exc

    if not isinstance(event, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le webhook doit contenir un objet JSON.",
        )

    event_name = event.get("event") or event.get("type") or event.get("name")
    provider_transaction_id = (
        event.get("transactionId")
        or event.get("transaction_id")
        or event.get("id")
    )

    if not isinstance(provider_transaction_id, str) or not provider_transaction_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifiant de transaction KKiaPay manquant.",
        )
    provider_transaction_id = provider_transaction_id.strip()

    result = await session.execute(
        select(Transaction).where(
            Transaction.provider == PAYMENT_PROVIDER,
            Transaction.provider_transaction_id == provider_transaction_id,
            Transaction.type == TransactionType.PAYMENT,
        )
    )
    transaction = result.scalars().first()

    if transaction is None:
        # KKiaPay peut notifier avant que /confirm ait enregistré l'identifiant.
        # On accuse réception pour éviter des retries inutiles, mais on ne marque
        # surtout pas l'événement comme traité côté paiement.
        logger.warning(
            "Webhook KKiaPay reçu pour une transaction locale inconnue (event=%s).",
            event_name,
        )
        return {"received": True, "processed": False}

    # La confirmation appelle la vérification serveur KKiaPay. Toute erreur
    # remonte afin que KKiaPay puisse réessayer le webhook.
    await confirm_payment(
        transaction_ref=transaction.transaction_ref,
        provider_transaction_id=provider_transaction_id,
        user_id=transaction.user_id,
        session=session,
    )

    return {
        "received": True,
        "processed": True,
        "event": event_name,
    }