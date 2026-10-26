# app/services/email.py

import logging
import os
from html import escape
from urllib.parse import urlencode

import resend

from app.config import settings


logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key

EMAIL_FROM = os.getenv(
    "EMAIL_FROM",
    "bestreservs <notifications@contact.bestreservs.com>",
)

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000",
).rstrip("/")


# ============================================================
# ENVOI CENTRALISÉ
# ============================================================

def send_email(
    *,
    email: str,
    subject: str,
    html_body: str,
) -> dict:

    if not settings.resend_api_key:
        raise RuntimeError(
            "La clé API Resend n'est pas configurée."
        )

    response = resend.Emails.send(
        {
            "from": EMAIL_FROM,
            "to": [email],
            "subject": subject,
            "html": html_body,
        }
    )

    logger.info(
        "Email envoyé à %s : %s",
        email,
        subject,
    )

    return response


# ============================================================
# TEMPLATE HTML COMMUN
# ============================================================

def get_email_template(
    content: str,
    title: str,
) -> str:
    safe_title = escape(title)

    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >
        <title>{safe_title}</title>
        <style>
            body {{
                font-family: Helvetica, Arial, sans-serif;
                background-color: #f9f9f9;
                margin: 0;
                padding: 0;
                color: #333;
            }}

            .container {{
                max-width: 600px;
                margin: 20px auto;
                background: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid #eeeeee;
            }}

            .header {{
                background-color: #1a1a1a;
                padding: 30px;
                text-align: center;
                color: #d4af37;
            }}

            .header h1 {{
                margin: 0;
                font-size: 28px;
                letter-spacing: 2px;
                text-transform: uppercase;
            }}

            .content {{
                padding: 32px;
                line-height: 1.6;
                font-size: 16px;
            }}

            .footer {{
                background-color: #f1f1f1;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #777;
            }}

            .btn {{
                display: inline-block;
                background-color: #d4af37;
                color: #ffffff !important;
                padding: 14px 28px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: bold;
                margin-top: 20px;
            }}

            .otp-box {{
                background: #f4f4f4;
                border: 2px dashed #d4af37;
                padding: 20px;
                text-align: center;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 5px;
                margin: 20px 0;
                color: #1a1a1a;
            }}

            .brand {{
                color: #d4af37;
                font-weight: bold;
            }}

            .details {{
                background: #f8f8f8;
                padding: 16px;
                border-radius: 6px;
                margin: 20px 0;
            }}
        </style>
    </head>

    <body>
        <div class="container">
            <div class="header">
                <h1>BESTRESERVS</h1>
                <p>
                    Découvrez et réservez les meilleures adresses.
                </p>
            </div>

            <div class="content">
                <h2 style="color: #1a1a1a;">
                    {safe_title}
                </h2>

                {content}

                <p>
                    À très bientôt,<br>
                    L'équipe <span class="brand">BestReservs</span>
                </p>
            </div>

            <div class="footer">
                <p>
                    &copy; 2026 BestReservs. Tous droits réservés.<br>
                    Cotonou, Bénin
                </p>
            </div>
        </div>
    </body>
    </html>
    """


# ============================================================
# AUTHENTIFICATION
# ============================================================

def send_otp_email(
    email: str,
    otp: str,
) -> dict:
    safe_otp = escape(str(otp))

    content = f"""
        <p>Bonjour,</p>

        <p>
            Bienvenue sur <strong>BestReservs</strong> !
        </p>

        <p>
            Pour finaliser votre inscription,
            utilisez le code de vérification ci-dessous :
        </p>

        <div class="otp-box">{safe_otp}</div>

        <p style="font-size: 14px; color: #666;">
            Ce code expire dans 10 minutes.
            Si vous n'êtes pas à l'origine de cette demande,
            vous pouvez ignorer cet email.
        </p>
    """

    return send_email(
        email=email,
        subject="Votre code de sécurité BestReservs",
        html_body=get_email_template(
            content,
            "Vérification de votre compte",
        ),
    )


def send_confirmation_email(
    email: str,
    name: str,
) -> dict:
    safe_name = escape(name)

    content = f"""
        <p>
            Bonjour {safe_name},
        </p>

        <p>
            Bienvenue sur BestReservs !
            Votre compte est désormais actif.
        </p>

        <p>Vous pouvez dès maintenant :</p>

        <ul>
            <li>Découvrir des établissements.</li>
            <li>Comparer les offres et les tarifs.</li>
            <li>Effectuer vos réservations en ligne.</li>
        </ul>
    """

    return send_email(
        email=email,
        subject="Bienvenue sur BestReservs !",
        html_body=get_email_template(
            content,
            f"Bienvenue parmi nous, {name}",
        ),
    )


def send_reset_password_email(
    email: str,
    token: str,
) -> dict:
    query = urlencode({"token": token})
    reset_link = f"{FRONTEND_URL}/reset-password?{query}"

    content = f"""
        <p>Bonjour,</p>

        <p>
            Vous avez demandé la réinitialisation
            du mot de passe de votre compte BestReservs.
        </p>

        <p>
            Cliquez sur le bouton ci-dessous pour choisir
            un nouveau mot de passe.
        </p>

        <div style="text-align: center; margin: 35px 0;">
            <a href="{escape(reset_link, quote=True)}"
               class="btn">
                Réinitialiser mon mot de passe
            </a>
        </div>

        <p>
            Si vous n'êtes pas à l'origine de cette demande,
            vous pouvez ignorer cet email.
        </p>
    """

    return send_email(
        email=email,
        subject="Réinitialisation du mot de passe BestReservs",
        html_body=get_email_template(
            content,
            "Réinitialisation de votre mot de passe",
        ),
    )


# ============================================================
# RÉSERVATIONS
# ============================================================

def send_reservation_created_email(
    *,
    email: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
    start_date: str,
    end_date: str,
    amount: str,
) -> dict:
    content = f"""
        <p>Bonjour {escape(name)},</p>

        <p>
            Nous avons bien reçu votre demande de réservation.
        </p>

        <div class="details">
            <p>
                <strong>Référence :</strong>
                {escape(reservation_reference)}
            </p>
            <p>
                <strong>Établissement :</strong>
                {escape(establishment_name)}
            </p>
            <p>
                <strong>Arrivée :</strong>
                {escape(start_date)}
            </p>
            <p>
                <strong>Départ :</strong>
                {escape(end_date)}
            </p>
            <p>
                <strong>Montant :</strong>
                {escape(amount)}
            </p>
        </div>

        <p>
            Vous pourrez consulter l'évolution de votre réservation
            depuis votre compte BestReservs.
        </p>
    """

    return send_email(
        email=email,
        subject=(
            f"Réservation reçue - {reservation_reference}"
        ),
        html_body=get_email_template(
            content,
            "Votre demande de réservation",
        ),
    )


def send_reservation_confirmed_email(
    *,
    email: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
    start_date: str,
    end_date: str,
) -> dict:
    content = f"""
        <p>Bonjour {escape(name)},</p>

        <p>
            Bonne nouvelle !
            Votre réservation a été confirmée.
        </p>

        <div class="details">
            <p>
                <strong>Référence :</strong>
                {escape(reservation_reference)}
            </p>
            <p>
                <strong>Établissement :</strong>
                {escape(establishment_name)}
            </p>
            <p>
                <strong>Arrivée :</strong>
                {escape(start_date)}
            </p>
            <p>
                <strong>Départ :</strong>
                {escape(end_date)}
            </p>
        </div>

        <p>
            Merci d'avoir choisi BestReservs.
            Nous vous souhaitons un excellent séjour !
        </p>
    """

    return send_email(
        email=email,
        subject=(
            f"Réservation confirmée - {reservation_reference}"
        ),
        html_body=get_email_template(
            content,
            "Votre réservation est confirmée !",
        ),
    )


def send_reservation_cancelled_email(
    *,
    email: str,
    name: str,
    reservation_reference: str,
    establishment_name: str,
    cancellation_reason: str | None = None,
) -> dict:
    reason_html = ""

    if cancellation_reason:
        reason_html = f"""
            <p>
                <strong>Motif :</strong>
                {escape(cancellation_reason)}
            </p>
        """

    content = f"""
        <p>Bonjour {escape(name)},</p>

        <p>
            Votre réservation a été annulée.
        </p>

        <div class="details">
            <p>
                <strong>Référence :</strong>
                {escape(reservation_reference)}
            </p>
            <p>
                <strong>Établissement :</strong>
                {escape(establishment_name)}
            </p>
            {reason_html}
        </div>

        <p>
            Si un paiement a été effectué,
            les éventuelles modalités de remboursement
            dépendent de votre réservation et des règles applicables.
        </p>

        <p>
            Pour toute question, contactez notre équipe.
        </p>
    """

    return send_email(
        email=email,
        subject=(
            f"Réservation annulée - {reservation_reference}"
        ),
        html_body=get_email_template(
            content,
            "Annulation de votre réservation",
        ),
    )


# ============================================================
# PAIEMENTS
# ============================================================

def send_payment_success_email(
    *,
    email: str,
    name: str,
    reservation_reference: str,
    amount: str,
    transaction_reference: str,
) -> dict:
    content = f"""
        <p>Bonjour {escape(name)},</p>

        <p>
            Nous confirmons la réception de votre paiement.
        </p>

        <div class="details">
            <p>
                <strong>Réservation :</strong>
                {escape(reservation_reference)}
            </p>
            <p>
                <strong>Montant payé :</strong>
                {escape(amount)}
            </p>
            <p>
                <strong>Référence de transaction :</strong>
                {escape(transaction_reference)}
            </p>
        </div>

        <p>
            Merci d'utiliser BestReservs !
        </p>
    """

    return send_email(
        email=email,
        subject=(
            f"Paiement confirmé - {reservation_reference}"
        ),
        html_body=get_email_template(
            content,
            "Votre paiement a été confirmé",
        ),
    )


def send_refund_email(
    *,
    email: str,
    name: str,
    reservation_reference: str,
    amount: str,
) -> dict:
    content = f"""
        <p>Bonjour {escape(name)},</p>

        <p>
            Le remboursement associé à votre réservation
            a été effectué.
        </p>

        <div class="details">
            <p>
                <strong>Réservation :</strong>
                {escape(reservation_reference)}
            </p>
            <p>
                <strong>Montant remboursé :</strong>
                {escape(amount)}
            </p>
        </div>

        <p>
            Selon votre banque ou votre opérateur de paiement,
            le délai d'apparition des fonds peut varier.
        </p>
    """

    return send_email(
        email=email,
        subject=(
            f"Remboursement effectué - {reservation_reference}"
        ),
        html_body=get_email_template(
            content,
            "Confirmation de remboursement",
        ),
    )