import resend
from app.config import settings

resend.api_key = settings.resend_api_key

def get_email_template(content: str, title: str):
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f9f9f9; margin: 0; padding: 0; color: #333; }}
            .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #eeeeee; }}
            .header {{ background-color: #1a1a1a; padding: 30px; text-align: center; color: #d4af37; }}
            .header h1 {{ margin: 0; font-size: 28px; letter-spacing: 2px; text-transform: uppercase; }}
            .content {{ padding: 40px; line-height: 1.6; font-size: 16px; }}
            .footer {{ background-color: #f1f1f1; padding: 20px; text-align: center; font-size: 12px; color: #777; }}
            .btn {{ display: inline-block; background-color: #d4af37; color: #ffffff !important; padding: 14px 28px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 20px; }}
            .otp-box {{ background: #f4f4f4; border: 2px dashed #d4af37; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; margin: 20px 0; color: #1a1a1a; }}
            .brand {{ color: #d4af37; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>BESTRESERV</h1>
                <p style="margin: 5px 0 0; font-size: 12px; color: #ffffff; opacity: 0.8;">La plateforme de référence pour découvrir et réserver les meilleures adresses au Bénin.</p>
            </div>
            <div class="content">
                <h2 style="color: #1a1a1a;">{title}</h2>
                {content}
                <p>À très bientôt,<br>L'équipe <span class="brand">BestReserv</span></p>
            </div>
            <div class="footer">
                <p>&copy; 2026 BestReserv. Tous droits réservés.<br>Cotonou, Bénin</p>
            </div>
        </div>
    </body>
    </html>
    """

def send_otp_email(email: str, otp: str):
    title = "Vérification de votre compte"
    content = f"""
        <p>Bonjour,</p>
        <p>Bienvenue sur <strong>BestReserv</strong> 👋</>
        <p> Pour finaliser votre inscription, veuillez utiliser le code de vérification ci-dessous :</p>
        <div class="otp-box">{otp}</div>
        <p style="font-size: 14px; color: #666;">Ce code expirera dans 10 minutes. Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.</p>
    """
    
    html_body = get_email_template(content, title)
    
    resend.Emails.send({
        "from": "BestReserv <onboarding@resend.dev>", 
        "to": email,
        "subject": "Votre code de sécurité BestReserv",
        "html": html_body,
    })

def send_confirmation_email(email: str, name: str):
    title = f"Bienvenue parmi nous, {name} 🎉"
    content = f"""
        <p>C’est un plaisir de vous accompagner dans la découverte et la réservation des meilleurs établissements, simplement et en toute confiance.</p>
        <p>Votre compte est désormais actif. Vous pouvez dès à présent :</p>
       <ul>
         <li>Découvrir des établissements adaptés à vos envies</li>
         <li>Comparer les offres et les tarifs</li>
         <li>Réserver facilement en quelques clics</li>
       </ul>
    """
    
    html_body = get_email_template(content, title)
    
    resend.Emails.send({
        "from": "BestReserv <onboarding@resend.dev>",
        "to": email,
        "subject": "Prêt à découvrir le monde des réservations ? Votre compte BestReserv est prêt !",
        "html": html_body,
    })


def send_reset_password_email(email: str, token: str):
    reset_link = f"http://127.0.0.1:8000/api/v1/reset-password?token={token}"
    
    title = "Réinitialisation de votre mot de passe"
    
    content = f"""
        <p>Bonjour,</p>
        <p>Vous avez demandé la réinitialisation du mot de passe de votre compte <strong>BestReserv</strong>.</p>
        <p>Pour choisir un nouveau mot de passe, veuillez cliquer sur le bouton ci-dessous. Attention, ce lien n'est valable que pendant <strong>30 minutes</strong>.</p>
        
        <div style="text-align: center; margin: 35px 0;">
            <a href="{reset_link}" 
               style="background-color: #d4af37; color: #ffffff !important; padding: 15px 30px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block; letter-spacing: 1px;">
               RÉINITIALISER MON MOT DE PASSE
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email en toute sécurité. Votre mot de passe actuel restera inchangé.</p>
    """
    
    # On utilise la fonction de template master qu'on a définie plus haut
    html_body = get_email_template(content, title)
    
    resend.Emails.send({
        "from": "BestReserv <onboarding@resend.dev>", # À remplacer par ton domaine dès que tu l'as
        "to": email,
        "subject": "Réinitialisation de mot de passe - BestReserv",
        "html": html_body
    })