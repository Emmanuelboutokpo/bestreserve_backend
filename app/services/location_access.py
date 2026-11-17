import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.enums import PaymentMethod, PaymentStatus, TransactionType
from app.models.location_access_payment import LocationAccessPayment
from app.models.transaction import Transaction
from app.models.user import User
from app.services.payment import (
    ONLINE_PAYMENT_METHODS,
    PAYMENT_PROVIDER,
    get_remote_value,
    money,
    verify_remote_transaction,
)
from app.services.notifi_dispatcher import notify_location_access_payment

logger = logging.getLogger(__name__)

LOCATION_ACCESS_AMOUNT = Decimal("500.00")


def _checkout_response(payment: LocationAccessPayment) -> dict:
    if not settings.kkiapay_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La clé publique KKiaPay n'est pas configurée.",
        )

    return {
        "transaction_ref": payment.transaction_ref,
        "public_key": settings.kkiapay_public_key,
        "partner_id": payment.transaction_ref,
        "amount": int(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "sandbox": settings.kkiapay_sandbox,
        "provider_transaction_id": payment.provider_transaction_id,
        "requires_widget": (
            payment.status == PaymentStatus.EN_ATTENTE
            and not payment.provider_transaction_id
        ),
    }


async def has_location_access(user_id: UUID, session: AsyncSession) -> bool:
    result = await session.execute(
        select(LocationAccessPayment.id)
        .where(
            LocationAccessPayment.user_id == user_id,
            LocationAccessPayment.status == PaymentStatus.PAYE,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_location_access_status(
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    result = await session.execute(
        select(LocationAccessPayment)
        .where(
            LocationAccessPayment.user_id == user_id,
            LocationAccessPayment.status == PaymentStatus.PAYE,
        )
        .order_by(LocationAccessPayment.updated_at.desc())
        .limit(1)
    )
    payment = result.scalars().first()
    return {
        "has_access": payment is not None,
        "purchased_at": payment.updated_at if payment is not None else None,
    }


async def create_location_access_payment(
    *,
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

    try:
        await session.execute(
            select(User.id).where(User.id == user_id).with_for_update()
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

        result = await session.execute(
            select(LocationAccessPayment)
            .where(
                LocationAccessPayment.idempotency_key == idempotency_key
            )
            .with_for_update()
        )
        existing = result.scalars().first()
        if existing is not None:
            if (
                existing.user_id != user_id
                or existing.payment_method != payment_method
                or existing.amount != LOCATION_ACCESS_AMOUNT
                or existing.currency != "XOF"
                or existing.provider != PAYMENT_PROVIDER
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cette Idempotency-Key est déjà associée à une autre opération.",
                )
            if existing.status == PaymentStatus.ECHOUE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cette tentative a échoué. Utilisez une nouvelle "
                        "Idempotency-Key pour réessayer."
                    ),
                )
            await session.commit()
            return _checkout_response(existing)

        if await has_location_access(user_id, session):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="L'accès aux localisations est déjà activé pour ce compte.",
            )

        result = await session.execute(
            select(LocationAccessPayment)
            .where(
                LocationAccessPayment.user_id == user_id,
                LocationAccessPayment.status == PaymentStatus.EN_ATTENTE,
            )
            .with_for_update()
        )
        if result.scalars().first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Un paiement est déjà en attente. Réutilisez son "
                    "Idempotency-Key pour le reprendre."
                ),
            )

        payment = LocationAccessPayment(
            user_id=user_id,
            amount=LOCATION_ACCESS_AMOUNT,
            currency="XOF",
            payment_method=payment_method,
            provider=PAYMENT_PROVIDER,
            status=PaymentStatus.EN_ATTENTE,
            idempotency_key=idempotency_key,
        )
        session.add(payment)
        await session.flush()
        await session.commit()
        await session.refresh(payment)
        return _checkout_response(payment)
    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        logger.warning("Conflit d'idempotence pendant le paiement d'accès.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Un paiement concurrent existe déjà. Réutilisez "
                "l'Idempotency-Key initiale."
            ),
        ) from exc
    except Exception:
        await session.rollback()
        logger.exception("Erreur lors de l'initialisation du paiement d'accès.")
        raise


async def confirm_location_access_payment(
    *,
    transaction_ref: str,
    provider_transaction_id: str,
    user_id: UUID,
    session: AsyncSession,
) -> LocationAccessPayment:
    provider_transaction_id = provider_transaction_id.strip()
    if not provider_transaction_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="L'identifiant de transaction KKiaPay est obligatoire.",
        )

    try:
        result = await session.execute(
            select(LocationAccessPayment)
            .where(
                LocationAccessPayment.transaction_ref == transaction_ref,
                LocationAccessPayment.user_id == user_id,
                LocationAccessPayment.provider == PAYMENT_PROVIDER,
            )
            .with_for_update()
        )
        payment = result.scalars().first()
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paiement d'accès introuvable.",
            )

        if payment.status == PaymentStatus.PAYE:
            if payment.provider_transaction_id != provider_transaction_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ce paiement est déjà associé à une autre transaction KKiaPay.",
                )
            await session.commit()
            return payment

        if payment.status != PaymentStatus.EN_ATTENTE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette tentative de paiement n'est plus en attente.",
            )

        if (
            payment.provider_transaction_id
            and payment.provider_transaction_id != provider_transaction_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="L'identifiant KKiaPay ne correspond pas à cette tentative.",
            )

        result = await session.execute(
            select(Transaction.id).where(
                Transaction.provider == PAYMENT_PROVIDER,
                Transaction.provider_transaction_id == provider_transaction_id,
                Transaction.type == TransactionType.PAYMENT,
            )
        )
        if result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette transaction KKiaPay est déjà utilisée.",
            )

        result = await session.execute(
            select(LocationAccessPayment.id).where(
                LocationAccessPayment.provider == PAYMENT_PROVIDER,
                LocationAccessPayment.provider_transaction_id
                == provider_transaction_id,
                LocationAccessPayment.id != payment.id,
            )
        )
        if result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette transaction KKiaPay est déjà utilisée.",
            )

        remote = await verify_remote_transaction(provider_transaction_id)
        remote_id = get_remote_value(remote, "transactionId", "transaction_id", "id")
        remote_status = str(get_remote_value(remote, "status") or "").strip().upper()

        if str(remote_id or "") != provider_transaction_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La référence de transaction ne correspond pas.",
            )

        try:
            remote_amount = money(get_remote_value(remote, "amount"))
        except (ValueError, InvalidOperation, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="KKiaPay a renvoyé un montant invalide.",
            ) from exc

        if remote_amount != LOCATION_ACCESS_AMOUNT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le montant vérifié ne correspond pas aux 500 FCFA attendus.",
            )

        payment.provider_transaction_id = provider_transaction_id
        if remote_status == "FAILED":
            payment.status = PaymentStatus.ECHOUE
        elif remote_status == "SUCCESS":
            payment.status = PaymentStatus.PAYE
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "KKiaPay ne confirme pas encore le succès du paiement. "
                    "Réessayez la vérification ultérieurement."
                ),
            )

        await session.commit()
        await session.refresh(payment)
        if payment.status == PaymentStatus.PAYE:
            try:
                user_result = await session.execute(
                    select(User)
                    .options(selectinload(User.profile))
                    .where(User.id == payment.user_id)
                )
                user = user_result.scalars().first()
                if user is not None and user.email:
                    profile = user.profile
                    name = (
                        " ".join(
                            part
                            for part in (
                                profile.firstName if profile else None,
                                profile.lastName if profile else None,
                            )
                            if part
                        )
                        or "Client"
                    )
                    notify_location_access_payment(
                        recipient=user.email,
                        name=name,
                        amount=f"{payment.amount} {payment.currency}",
                        transaction_reference=provider_transaction_id,
                    )
                else:
                    logger.warning(
                        "Email de confirmation d'accès indisponible pour le client %s.",
                        payment.user_id,
                    )
            except Exception:
                logger.exception(
                    "Impossible de préparer l'email de confirmation "
                    "du paiement d'accès %s.",
                    payment.transaction_ref,
                )
        return payment
    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        logger.warning("Conflit d'unicité lors de la confirmation du paiement d'accès.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette référence KKiaPay est déjà associée à un paiement.",
        ) from exc
    except Exception:
        await session.rollback()
        logger.exception("Erreur lors de la confirmation du paiement d'accès.")
        raise
