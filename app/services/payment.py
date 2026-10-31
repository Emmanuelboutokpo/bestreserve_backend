# app/services/payment.py

import asyncio
import hmac
import logging
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_

from kkiapay import Kkiapay

from app.emails.email import send_payment_success_email

from app.services.notifi_dispatcher import dispatch_email

from app.config import settings
from app.models.base import utc_now
from app.models.enums import (
    PaymentMethod,
    PaymentStatus,
    ReservationStatus,
    TransactionType,
)

from app.models.user import User
from app.models.reservation import Reservation
from app.models.transaction import Transaction
from app.models.establishment import Establishment

logger = logging.getLogger(__name__)

PAYMENT_PROVIDER = "KKIAPAY"
ZERO = Decimal("0.00")
CENT = Decimal("0.01")

ONLINE_PAYMENT_METHODS = {
    PaymentMethod.MOBILE_MONEY,
    PaymentMethod.CARTE_BANCAIRE,
}


# ============================================================
# CONFIGURATION DU SDK
# ============================================================

def get_kkiapay_client() -> Kkiapay:
    """Construit le client serveur KKiaPay à partir de la configuration."""
    public_key = settings.kkiapay_public_key
    private_key = settings.kkiapay_private_key
    secret_key = settings.kkiapay_secret_key

    if not all((public_key, private_key, secret_key)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de paiement KKiaPay n'est pas configuré.",
        )

    return Kkiapay(
        public_key,
        private_key,
        secret_key,
        sandbox=settings.kkiapay_sandbox,
    )


def verify_webhook_secret(received_secret: str | None) -> bool:

    expected_secret = settings.kkiapay_webhook_secret

    if not expected_secret or not received_secret:
        return False

    return hmac.compare_digest(expected_secret, received_secret)


# ============================================================
# OUTILS
# ============================================================

def money(value: Any) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(CENT)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Montant invalide.") from exc

    if not result.is_finite():
        raise ValueError("Le montant doit être un nombre fini.")

    return result


def get_remote_value(transaction: Any, *names: str) -> Any:
    for name in names:
        if isinstance(transaction, dict):
            value = transaction.get(name)
        else:
            value = getattr(transaction, name, None)

        if value is not None:
            return value

    return None


async def verify_remote_transaction(provider_transaction_id: str) -> Any:
    if not provider_transaction_id or not provider_transaction_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="L'identifiant de transaction KKiaPay est obligatoire.",
        )

    client = get_kkiapay_client()

    try:
        return await asyncio.to_thread(
            client.verify_transaction,
            provider_transaction_id.strip(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Échec de vérification d'une transaction KKiaPay.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de vérifier le paiement auprès de KKiaPay.",
        ) from exc


def _checkout_response(
    transaction: Transaction,
    reservation: Reservation,
) -> dict:

    if not settings.kkiapay_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La clé publique KKiaPay n'est pas configurée.",
        )

    has_provider_transaction = bool(transaction.provider_transaction_id)

    return {
        "transaction_ref": transaction.transaction_ref,
        "public_key": settings.kkiapay_public_key,
        "partner_id": transaction.transaction_ref,
        "amount": int(money(transaction.amount)),
        "currency": transaction.currency,
        "status": transaction.status,
        "sandbox": settings.kkiapay_sandbox,
        "provider_transaction_id": transaction.provider_transaction_id,
        "requires_widget": (
            transaction.status == PaymentStatus.EN_ATTENTE
            and not has_provider_transaction
        ),
    }


# ============================================================
# INITIALISATION / REPRISE DU PAIEMENT
# ============================================================

async def create_payment(
    *,
    reservation_id: UUID,
    user_id: UUID,
    payment_method: PaymentMethod,
    idempotency_key: str,
    session: AsyncSession,
) -> dict:
    
    idempotency_key = idempotency_key.strip()

    if not 16 <= len(idempotency_key) <= 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key doit contenir entre 16 et 255 caractères.",
        )

    if not all(
        (
            settings.kkiapay_public_key,
            settings.kkiapay_private_key,
            settings.kkiapay_secret_key,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KKiaPay n'est pas entièrement configuré.",
        )

    if payment_method not in ONLINE_PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "KKiaPay accepte uniquement les paiements par "
                "Mobile Money ou carte bancaire."
            ),
        )

    try:
    
        result = await session.execute(
            select(Reservation)
            .where(
                Reservation.id == reservation_id,
                Reservation.user_id == user_id,
            )
            .with_for_update()
        )
        reservation = result.scalars().first()

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Réservation introuvable.",
            )

        result = await session.execute(
            select(Transaction)
            .where(Transaction.idempotency_key == idempotency_key)
            .with_for_update()
        )
        existing = result.scalars().first()

        if existing is not None:
            same_operation = (
                existing.user_id == user_id
                and existing.reservation_id == reservation.id
                and existing.type == TransactionType.PAYMENT
                and existing.provider == PAYMENT_PROVIDER
                and existing.payment_method == payment_method
                and existing.currency == reservation.currency
            )

            if not same_operation:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cette Idempotency-Key est déjà associée "
                        "à une autre opération."
                    ),
                )

            if existing.status == PaymentStatus.ECHOUE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cette tentative a échoué. Utilisez une nouvelle "
                        "Idempotency-Key pour démarrer une nouvelle tentative."
                    ),
                )

            if existing.status == PaymentStatus.REMBOURSE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cette transaction a été remboursée.",
                )

            if existing.status not in {
                PaymentStatus.EN_ATTENTE,
                PaymentStatus.PAYE,
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cette tentative ne peut pas être reprise.",
                )

            if money(existing.amount) <= ZERO:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Le montant de la transaction existante est invalide.",
                )

            await session.commit()
            return _checkout_response(existing, reservation)

        if reservation.status not in {
            ReservationStatus.EN_ATTENTE,
            ReservationStatus.CONFIRMEE,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette réservation ne peut pas être payée.",
            )

        if reservation.payment_status == PaymentStatus.PAYE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette réservation est déjà intégralement payée.",
            )

        if reservation.payment_status not in {
            PaymentStatus.EN_ATTENTE,
            PaymentStatus.ECHOUE,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le statut actuel ne permet pas de démarrer un paiement.",
            )

        amount = money(reservation.balance_due)

        if amount <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aucun solde restant à payer.",
            )

        if amount != amount.to_integral_value():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le montant XOF doit être un nombre entier.",
            )

        if reservation.currency != "XOF":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cette intégration KKiaPay est configurée pour le XOF.",
            )

        result = await session.execute(
            select(Transaction)
            .where(
                Transaction.reservation_id == reservation.id,
                Transaction.user_id == user_id,
                Transaction.provider == PAYMENT_PROVIDER,
                Transaction.type == TransactionType.PAYMENT,
                Transaction.status == PaymentStatus.EN_ATTENTE,
            )
            .with_for_update()
        )
        pending = result.scalars().first()

        if pending is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Une tentative KKiaPay est déjà en attente. "
                    "Réutilisez son Idempotency-Key au lieu d'en créer une autre."
                ),
            )

        transaction = Transaction(
            user_id=user_id,
            reservation_id=reservation.id,
            type=TransactionType.PAYMENT,
            amount=amount,
            currency=reservation.currency,
            payment_method=payment_method,
            provider=PAYMENT_PROVIDER,
            status=PaymentStatus.EN_ATTENTE,
            idempotency_key=idempotency_key,
            metadata_json={
                "reservation_reference": reservation.reference,
            },
        )

        reservation.payment_method = payment_method
        reservation.payment_provider = PAYMENT_PROVIDER
        reservation.payment_status = PaymentStatus.EN_ATTENTE

        session.add(transaction)

        try:
            await session.flush()
            await session.commit()
            await session.refresh(transaction)
        except IntegrityError as exc:
            await session.rollback()
            logger.warning(
                "Conflit d'idempotence pendant la création d'un paiement KKiaPay."
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Une tentative concurrente existe déjà. "
                    "Réutilisez l'Idempotency-Key initiale et consultez son statut."
                ),
            ) from exc

        return _checkout_response(transaction, reservation)

    except HTTPException:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        logger.exception("Erreur lors de l'initialisation du paiement KKiaPay.")
        raise

# ============================================================
# NOTIFICATIONS DE PAIEMENT
# ============================================================

async def _notify_payment_confirmed(
    *,
    transaction: Transaction,
    reservation: Reservation,
    session: AsyncSession,
) -> None:
 
    try:
        result = await session.execute(
            select(User).where(User.id == transaction.user_id)
        )
        user = result.scalars().first()

        if user is None or not user.email:
            logger.warning(
                "Impossible de notifier le paiement : utilisateur "
                "introuvable ou adresse e-mail absente. Transaction=%s",
                transaction.transaction_ref,
            )
            return

        first_name = getattr(user, "first_name", None)
        last_name = getattr(user, "last_name", None)

        display_name = " ".join(
            part
            for part in (first_name, last_name)
            if part
        ) or "Client"

        transaction_reference = (
            transaction.provider_transaction_id
            or transaction.transaction_ref
        )

        await asyncio.to_thread(
            dispatch_email,
            recipient=user.email,
            event_name="payment.success",
            sender=send_payment_success_email,
            name=display_name,
            reservation_reference=reservation.reference,
            amount=str(transaction.amount),
            transaction_reference=transaction_reference,
        )

        logger.info(
            "Notification de paiement exécutée. Transaction=%s",
            transaction.transaction_ref,
        )

    except Exception:
        logger.exception(
            "Erreur de notification du paiement. Transaction=%s",
            transaction.transaction_ref,
        )

# ============================================================
# VÉRIFICATION ET COMPTABILISATION
# ============================================================

async def confirm_payment(
    *,
    transaction_ref: str,
    provider_transaction_id: str,
    user_id: UUID,
    session: AsyncSession,
) -> Transaction:

    provider_transaction_id = provider_transaction_id.strip()

    if not provider_transaction_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="L'identifiant de transaction KKiaPay est obligatoire.",
        )

    try:
        result = await session.execute(
            select(Transaction, Reservation)
            .join(
                Reservation,
                Reservation.id == Transaction.reservation_id,
            )
            .where(
                Transaction.transaction_ref == transaction_ref,
                Transaction.user_id == user_id,
                Transaction.provider == PAYMENT_PROVIDER,
                Transaction.type == TransactionType.PAYMENT,
            )
            .with_for_update(of=(Transaction, Reservation))
        )
        pair = result.first()

        if pair is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction BestRev introuvable.",
            )

        transaction, reservation = pair

    
        if transaction.status == PaymentStatus.PAYE:
            if transaction.provider_transaction_id != provider_transaction_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cette transaction est déjà associée à un autre "
                        "identifiant KKiaPay."
                    ),
                )

            await session.commit()
            return transaction

        if transaction.status != PaymentStatus.EN_ATTENTE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette tentative de paiement n'est plus en attente.",
            )

        if (
            transaction.provider_transaction_id
            and transaction.provider_transaction_id != provider_transaction_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="L'identifiant KKiaPay ne correspond pas à cette tentative.",
            )

        result = await session.execute(
            select(Transaction.id).where(
                Transaction.provider == PAYMENT_PROVIDER,
                Transaction.provider_transaction_id == provider_transaction_id,
                Transaction.id != transaction.id,
            )
        )
        if result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cette transaction KKiaPay est déjà associée "
                    "à une autre transaction BestRev."
                ),
            )

        remote = await verify_remote_transaction(provider_transaction_id)

        remote_id = get_remote_value(
            remote,
            "transactionId",
            "transaction_id",
            "id",
        )
        remote_status = str(
            get_remote_value(remote, "status") or ""
        ).strip().upper()
        remote_amount_raw = get_remote_value(remote, "amount")

        if str(remote_id or "") != provider_transaction_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La référence de transaction ne correspond pas.",
            )

        try:
            remote_amount = money(remote_amount_raw)
        except (ValueError, InvalidOperation, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="KKiaPay a renvoyé un montant invalide.",
            ) from exc

        if remote_amount != money(transaction.amount):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le montant vérifié ne correspond pas au montant attendu.",
            )

        if remote_status == "FAILED":
            transaction.provider_transaction_id = provider_transaction_id
            transaction.status = PaymentStatus.ECHOUE


            if reservation.payment_status != PaymentStatus.PAYE:
                reservation.payment_status = PaymentStatus.ECHOUE

            await session.commit()
            return transaction

        if remote_status != "SUCCESS":
            # Les transactions encore en attente restent en attente.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "KKiaPay ne confirme pas encore le succès du paiement. "
                    "Réessayez la vérification ultérieurement."
                ),
            )

        current_balance = money(reservation.balance_due)

        if current_balance < money(transaction.amount):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le montant dépasse le solde restant de la réservation.",
            )

        new_amount_paid = money(reservation.amount_paid + transaction.amount)
        new_balance_due = money(current_balance - transaction.amount)

        if new_amount_paid > money(reservation.total) or new_balance_due < ZERO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La mise à jour financière produirait un solde invalide.",
            )

        transaction.provider_transaction_id = provider_transaction_id
        transaction.status = PaymentStatus.PAYE

        reservation.amount_paid = new_amount_paid
        reservation.balance_due = new_balance_due
        reservation.payment_provider = PAYMENT_PROVIDER
        reservation.payment_reference = provider_transaction_id[:255]
        reservation.paid_at = reservation.paid_at or utc_now()

        reservation.payment_status = (
            PaymentStatus.PAYE
            if new_balance_due == ZERO
            else PaymentStatus.EN_ATTENTE
        )

        await session.commit()
        await session.refresh(transaction)


        await _notify_payment_confirmed(
            transaction=transaction,
            reservation=reservation,
            session=session,
        )
        
        return transaction

    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        logger.warning(
            "Conflit d'unicité lors de la confirmation d'un paiement KKiaPay."
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cette référence KKiaPay a déjà été associée à une transaction."
            ),
        ) from exc
    except Exception:
        await session.rollback()
        logger.exception("Erreur lors de la confirmation du paiement KKiaPay.")
        raise


def _enum_value(value: Any) -> str | None:
    """Convertit un enum en valeur exploitable par l'API."""
    if value is None:
        return None

    return str(value.value) if hasattr(value, "value") else str(value)


def _payment_to_dict(
    transaction: Transaction,
    reservation: Reservation,
    establishment: Establishment,
) -> dict[str, Any]:

    return {
        "id": transaction.id,
        "transaction_ref": transaction.transaction_ref,
        "provider_transaction_id": transaction.provider_transaction_id,

        "type": _enum_value(transaction.type),
        "amount": transaction.amount,
        "currency": transaction.currency,
        "payment_method": _enum_value(transaction.payment_method),
        "provider": transaction.provider,
        "status": _enum_value(transaction.status),

        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,

        # Informations sur la réservation
        "reservation": {
            "reference": reservation.reference,
            "establishment_name": establishment.name,
            "category": reservation.category,

            "reservation_date": reservation.reservation_date,
            "start_date": reservation.start_date,
            "end_date": reservation.end_date,

            "status": _enum_value(reservation.status),
            "payment_status": _enum_value(reservation.payment_status),

            "total": reservation.total,
            "amount_paid": reservation.amount_paid,
            "balance_due": reservation.balance_due,
        },

        # Informations sur le client
        "client": {
            "first_name": reservation.client_first_name,
            "last_name": reservation.client_last_name,
            "email": reservation.client_email,
            "phone": reservation.client_phone,
        },
    }

def _build_date_filters(
    start_date: date | None,
    end_date: date | None,
) -> list:
    """
    Construit les filtres de dates.
    La date de fin est incluse dans son intégralité.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date doit être antérieure ou égale à end_date.",
        )

    filters = []

    if start_date:
        start_datetime = datetime.combine(
            start_date,
            time.min,
            tzinfo=timezone.utc,
        )
        filters.append(Transaction.created_at >= start_datetime)

    if end_date:
        end_datetime = datetime.combine(
            end_date + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        filters.append(Transaction.created_at < end_datetime)

    return filters


def _parse_payment_status(value: str | None) -> PaymentStatus | None:
    """Valide le statut demandé dans les filtres."""
    if value is None:
        return None

    try:
        return PaymentStatus(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in PaymentStatus)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Statut invalide. Valeurs autorisées : {allowed}.",
        ) from exc


def _parse_transaction_type(
    value: str | None,
) -> TransactionType | None:
    """Valide le type de transaction demandé."""
    if value is None:
        return None

    try:
        return TransactionType(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in TransactionType)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Type invalide. Valeurs autorisées : {allowed}.",
        ) from exc


def _build_payment_filters(
    *,
    status_filter: str | None = None,
    transaction_type: str | None = None,
    provider: str | None = None,
    user_id: UUID | None = None,
    reservation_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
) -> list:
    """Centralise les filtres communs aux consultations administratives."""
    filters = _build_date_filters(start_date, end_date)

    parsed_status = _parse_payment_status(status_filter)
    parsed_type = _parse_transaction_type(transaction_type)

    if parsed_status is not None:
        filters.append(Transaction.status == parsed_status)

    if parsed_type is not None:
        filters.append(Transaction.type == parsed_type)

    if provider:
        filters.append(
            Transaction.provider == provider.strip().upper()
        )

    if user_id:
        filters.append(Transaction.user_id == user_id)

    if reservation_id:
        filters.append(Transaction.reservation_id == reservation_id)

    if search:
        term = f"%{search.strip()}%"

        filters.append(
            or_(
                Transaction.transaction_ref.ilike(term),
                Transaction.provider_transaction_id.ilike(term),
            )
        )

    return filters


# ============================================================
# LISTE DES TRANSACTIONS
# ============================================================

async def list_admin_payments(
    *,
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    transaction_type: str | None = None,
    provider: str | None = None,
    user_id: UUID | None = None,
    reservation_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
) -> dict[str, Any]:

    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La pagination demandée est invalide.",
        )

    filters = _build_payment_filters(
        status_filter=status_filter,
        transaction_type=transaction_type,
        provider=provider,
        user_id=user_id,
        reservation_id=reservation_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )

    # Nombre total de transactions
    count_result = await session.execute(
        select(func.count(Transaction.id)).where(*filters)
    )
    total = count_result.scalar_one()

    # Récupération des transactions, réservations et établissements
    result = await session.execute(
        select(Transaction, Reservation, Establishment)
        .join(
            Reservation,
            Reservation.id == Transaction.reservation_id,
        )
        .join(
            Establishment,
            Establishment.id == Reservation.establishment_id,
        )
        .where(*filters)
        .order_by(
            Transaction.created_at.desc(),
            Transaction.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = result.all()

    return {
        "items": [
            _payment_to_dict(
                transaction,
                reservation,
                establishment,
            )
            for transaction, reservation, establishment in rows
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        },
    }

# ============================================================
# DÉTAIL D'UNE TRANSACTION
# ============================================================

async def get_admin_payment(
    *,
    transaction_id: UUID,
    session: AsyncSession,
) -> dict[str, Any]:

    result = await session.execute(
        select(
            Transaction,
            Reservation,
            Establishment,
        )
        .join(
            Reservation,
            Reservation.id == Transaction.reservation_id,
        )
        .join(
            Establishment,
            Establishment.id == Reservation.establishment_id,
        )
        .where(Transaction.id == transaction_id)
    )

    pair = result.first()

    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction introuvable.",
        )

    transaction, reservation, establishment = pair

    return _payment_to_dict(
        transaction,
        reservation,
        establishment,
    )

# ============================================================
# STATISTIQUES DES PAIEMENTS
# ============================================================

async def get_admin_payment_stats(
    *,
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
) -> dict[str, Any]:

    date_filters = _build_date_filters(start_date, end_date)

    payment_filters = [
        *date_filters,
        Transaction.type == TransactionType.PAYMENT,
    ]

    refund_filters = [
        *date_filters,
        Transaction.type == TransactionType.REFUND,
    ]

    if provider:
        normalized_provider = provider.strip().upper()

        payment_filters.append(
            Transaction.provider == normalized_provider
        )
        refund_filters.append(
            Transaction.provider == normalized_provider
        )

    result = await session.execute(
        select(
            Transaction.currency,
            Transaction.status,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .where(*payment_filters)
        .group_by(
            Transaction.currency,
            Transaction.status,
        )
    )

    payments_by_currency: dict[str, dict[str, Any]] = {}

    for currency, payment_status, count, amount in result.all():
        currency_stats = payments_by_currency.setdefault(
            currency,
            {
                "by_status": {},
                "total_count": 0,
                "confirmed_amount": "0",
            },
        )

        status_name = _enum_value(payment_status)

        currency_stats["by_status"][status_name] = {
            "count": count,
            "amount": str(amount),
        }

        currency_stats["total_count"] += count

        if payment_status == PaymentStatus.PAYE:
            currency_stats["confirmed_amount"] = str(amount)

    refund_result = await session.execute(
        select(
            Transaction.currency,
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .where(
            *refund_filters,
            Transaction.status == PaymentStatus.REMBOURSE,
        )
        .group_by(Transaction.currency)
    )

    refunds_by_currency = {
        currency: {
            "count": count,
            "amount": str(amount),
        }
        for currency, count, amount in refund_result.all()
    }

    return {
        "payments_by_currency": payments_by_currency,
        "refunds_by_currency": refunds_by_currency,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "provider": provider,
        },
    }