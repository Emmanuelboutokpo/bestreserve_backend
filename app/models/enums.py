from enum import Enum


class UserRole(str, Enum):
    CLIENT = "CLIENT"
    PROPRIETAIRE = "PROPRIETAIRE"
    ADMIN = "ADMIN"


class UserStatus(str, Enum):
    ACTIF = "ACTIF"
    INACTIF = "INACTIF"
    EN_ATTENTE = "EN_ATTENTE"
    SUSPENDU = "SUSPENDU"


class UserProvider(str, Enum):
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"
    FACEBOOK = "FACEBOOK"


class LocationType(str, Enum):
    COUNTRY = "COUNTRY"
    REGION = "REGION"
    CITY = "CITY"
    DISTRICT = "DISTRICT"
    NEIGHBORHOOD = "NEIGHBORHOOD"


class EstablishmentStatus(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    PUBLIE = "PUBLIE"
    REJETE = "REJETE"
    SUSPENDU = "SUSPENDU"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RENTED = "RENTED"
    UNAVAILABLE = "UNAVAILABLE"


class PriceUnit(str, Enum):
    """
    Unités de tarification des établissements.

    Les anciennes valeurs sont conservées pour limiter
    les ruptures de compatibilité avec le code existant.
    """

    NUIT = "NUIT"
    PERSONNE = "PERSONNE"
    MOIS = "MOIS"

    # Unités complémentaires
    PERSONNE_NUIT = "PERSONNE_NUIT"
    GROUPE = "GROUPE"
    PRESTATION = "PRESTATION"
    HEURE = "HEURE"
    CRENEAU = "CRENEAU"


class ValidationStatus(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    EN_REVISION = "EN_REVISION"
    VALIDE = "VALIDE"
    REJETE = "REJETE"


class DocumentType(str, Enum):
    REGISTRE = "REGISTRE"
    PIECE_IDENTITE = "PIECE_IDENTITE"
    ATTESTATION_FISCALE = "ATTESTATION_FISCALE"
    CERTIFICAT_HYGIENE = "CERTIFICAT_HYGIENE"
    TITRE_PROPRIETE = "TITRE_PROPRIETE"
    AUTRE = "AUTRE"


class ReservationStatus(str, Enum):
    """
    Cycle de vie d'une réservation BestRev.

    Les transitions autorisées seront contrôlées par le service métier.
    """

    EN_ATTENTE = "EN_ATTENTE"
    CONFIRMEE = "CONFIRMEE"
    EN_COURS = "EN_COURS"
    TERMINEE = "TERMINEE"

    REFUSEE = "REFUSEE"
    ANNULEE = "ANNULEE"
    EXPIREE = "EXPIREE"


class PaymentMethod(str, Enum):
    CARTE_BANCAIRE = "CARTE_BANCAIRE"
    MOBILE_MONEY = "MOBILE_MONEY"
    VIREMENT = "VIREMENT"

    # Selon les conditions de paiement du partenaire
    SUR_PLACE = "SUR_PLACE"


class PaymentStatus(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    PAYE = "PAYE"
    REMBOURSE = "REMBOURSE"
    ECHOUE = "ECHOUE"


class TransactionType(str, Enum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"


class NotificationType(str, Enum):
    BOOKING = "BOOKING"
    PAYMENT = "PAYMENT"
    REMINDER = "REMINDER"
    REVIEW = "REVIEW"
    VALIDATION = "VALIDATION"
    SYSTEM = "SYSTEM"


class ContactSubject(str, Enum):
    GENERAL = "GENERAL"
    PARTENARIAT = "PARTENARIAT"
    SUPPORT = "SUPPORT"
    PRESSE = "PRESSE"
    AUTRE = "AUTRE"


class ContactStatus(str, Enum):
    NON_LU = "NON_LU"
    EN_COURS = "EN_COURS"
    TRAITE = "TRAITE"


class PaymentConditionType(str, Enum):
    PAIEMENT_INTEGRAL = "PAIEMENT_INTEGRAL"
    ACOMPTE = "ACOMPTE"
    SUR_PLACE = "SUR_PLACE"