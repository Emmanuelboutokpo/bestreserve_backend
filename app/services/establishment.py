import re
import unicodedata
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
from datetime import date, time

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    ActivityLog,
    Category,
    Establishment,
    EstablishmentAmenity,
    EstablishmentPaymentCondition,
    Location,
    Reservation,
    Review,
    SubCategory,
    User,
)
from app.models.enums import (
    EstablishmentStatus,
    ReservationStatus,
)


class EstablishmentService:
    """Centralise les opérations métier liées aux établissements."""

    MAX_IMAGE_BYTES = 10 * 1024 * 1024

    ACTIVE_RESERVATION_STATUSES = {
        ReservationStatus.CONFIRMEE,
        ReservationStatus.EN_COURS,
    }

    # ---------------------------------------------------------
    # REQUÊTES
    # ---------------------------------------------------------

    @staticmethod
    def _list_query(*, include_all_statuses: bool = False):
        query = (
            select(Establishment)
            .options(
                selectinload(Establishment.category),
                selectinload(Establishment.subcategory),
                selectinload(Establishment.location),
                selectinload(Establishment.photos),
                selectinload(
                    Establishment.amenity_links
                ).selectinload(EstablishmentAmenity.amenity),
            )
        )

        if not include_all_statuses:
            query = query.where(
                Establishment.status == EstablishmentStatus.PUBLIE
            )

        return query


    @staticmethod
    def _detail_query(*, include_all_statuses: bool = False):
        query = (
            select(Establishment)
            .options(
                selectinload(Establishment.category),
                selectinload(Establishment.subcategory),
                selectinload(Establishment.location),
                selectinload(Establishment.owner).selectinload(
                    User.profile
                ),
                selectinload(Establishment.photos),
                selectinload(
                    Establishment.amenity_links
                ).selectinload(EstablishmentAmenity.amenity),
                selectinload(
                    Establishment.payment_condition_links
                ).selectinload(
                    EstablishmentPaymentCondition.payment_condition
                ),
            )
        )

        if not include_all_statuses:
            query = query.where(
                Establishment.status == EstablishmentStatus.PUBLIE
            )

        return query

    @classmethod
    async def list_similar(
        cls,
        db: AsyncSession,
        establishment_id: UUID,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        # Récupérer l'établissement de référence.
        reference_result = await db.execute(
            select(Establishment).where(
                Establishment.id == establishment_id,
                Establishment.status == EstablishmentStatus.PUBLIE,
            )
        )
        reference = reference_result.scalar_one_or_none()

        if reference is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Établissement introuvable.",
            )

        # Chercher les établissements publiés de même catégorie,
        # sans inclure l'établissement de référence.
        query = cls._list_query().where(
            Establishment.id != establishment_id,
            Establishment.category_id == reference.category_id,
        )

        # Prioriser la même sous-catégorie si elle est définie.
        if reference.subcategory_id is not None:
            query = query.order_by(
                (
                    Establishment.subcategory_id
                    == reference.subcategory_id
                ).desc(),
                Establishment.rating.desc(),
            )
        else:
            query = query.order_by(
                Establishment.rating.desc()
            )

        result = await db.execute(query.limit(limit))
        establishments = result.scalars().unique().all()

        return [
            cls.serialize_list_item(establishment)
            for establishment in establishments
        ]

    # ---------------------------------------------------------
    # SÉRIALISATION DES RELATIONS
    # ---------------------------------------------------------

    @staticmethod
    def _serialize_model(obj) -> Optional[dict[str, Any]]:
        """
        Convertit les colonnes d'un modèle SQLAlchemy en dictionnaire.
        Évite de renvoyer directement les objets SQLAlchemy imbriqués.
        """
        if obj is None:
            return None

        return {
            column.key: getattr(obj, column.key)
            for column in obj.__mapper__.column_attrs
        }


    @classmethod
    def _extract_cover_photo(
        cls,
        establishment: Establishment,
    ) -> Optional[dict[str, Any]]:
        photos = list(establishment.photos or [])

        cover = next(
            (photo for photo in photos if photo.is_cover),
            None,
        )

        if cover is None and photos:
            cover = photos[0]

        if cover is None:
            return None

        return {
            "id": cover.id,
            "url": cover.url,
        }


    # ---------------------------------------------------------
    # SÉRIALISATION DE LA LISTE
    # ---------------------------------------------------------

    @classmethod
    def serialize_list_item(
        cls,
        establishment: Establishment,
    ) -> dict[str, Any]:
        amenities = [
            cls._serialize_model(link.amenity)
            for link in (establishment.amenity_links or [])
            if link.amenity is not None
        ]

        return {
            "id": establishment.id,
            "category_id": establishment.category_id,
            "subcategory_id": establishment.subcategory_id,
            "location_id": establishment.location_id,
            "name": establishment.name,
            "slug": establishment.slug,
            "description": establishment.description,
            "address": establishment.address,
            "latitude": establishment.latitude,
            "longitude": establishment.longitude,

            # Relations nécessaires à la liste
            "category": cls._serialize_model(
                establishment.category
            ),
            "subcategory": cls._serialize_model(
                establishment.subcategory
            ),
            "location": cls._serialize_model(
                establishment.location
            ),

            # Note et nombre d'avis
            "rating": establishment.rating,
            "reviews_count": establishment.reviews_count,

            # Équipements et image de couverture
            "amenities": amenities,
            "cover_photo": cls._extract_cover_photo(
                establishment
            ),

            # Informations principales
            "price": establishment.price,
            "price_per_night": establishment.price_per_night,
            "price_per_month": establishment.price_per_month,
            "price_unit": establishment.price_unit,
            "currency": establishment.currency,
            "capacity": establishment.capacity,
            "rooms_count": establishment.rooms_count,
            "cuisine_type": establishment.cuisine_type,
            "opening_hours": establishment.opening_hours,
            "area": establishment.area,
            "availability_status": establishment.availability_status,
            "created_at": establishment.created_at,
        }


    # ---------------------------------------------------------
    # SÉRIALISATION DU DÉTAIL COMPLET
    # ---------------------------------------------------------

    @classmethod
    def serialize_detail(
        cls,
        establishment: Establishment,
    ) -> dict[str, Any]:
        photos = list(establishment.photos or [])

        # Mettre la photo de couverture en premier,
        # puis trier les autres photos par date de création.
        photos.sort(
            key=lambda photo: (
                not getattr(photo, "is_cover", False),
                getattr(photo, "created_at", None) is None,
                getattr(photo, "created_at", None),
            )
        )

        serialized_photos = (
            [
                cls._serialize_model(photo)
                for photo in photos
            ]
            if photos
            else None
        )

        amenities = [
            cls._serialize_model(link.amenity)
            for link in (establishment.amenity_links or [])
            if link.amenity is not None
        ]

        payment_conditions = [
            cls._serialize_model(link.payment_condition)
            for link in (
                establishment.payment_condition_links or []
            )
            if link.payment_condition is not None
        ]

        owner = None

        if establishment.owner:
            profile = getattr(
                establishment.owner,
                "profile",
                None,
            )

            owner = {
                "id": establishment.owner.id,
                "first_name": (
                    profile.firstName if profile else None
                ),
                "last_name": (
                    profile.lastName if profile else None
                ),
                "avatar_url": profile.img if profile else None,
            }

        return {
            "id": establishment.id,
            "category_id": establishment.category_id,
            "subcategory_id": establishment.subcategory_id,
            "location_id": establishment.location_id,
            "name": establishment.name,
            "slug": establishment.slug,
            "description": establishment.description,
            "address": establishment.address,
            "latitude": establishment.latitude,
            "longitude": establishment.longitude,

            # Relations complètes
            "category": cls._serialize_model(
                establishment.category
            ),
            "subcategory": cls._serialize_model(
                establishment.subcategory
            ),
            "location": cls._serialize_model(
                establishment.location
            ),
            "owner": owner,
            "photos": serialized_photos,
            "amenities": amenities,
            "payment_conditions": payment_conditions,

            # Informations tarifaires et caractéristiques
            "price": establishment.price,
            "price_per_night": establishment.price_per_night,
            "price_per_month": establishment.price_per_month,
            "price_unit": establishment.price_unit,
            "currency": establishment.currency,
            "capacity": establishment.capacity,
            "rooms_count": establishment.rooms_count,
            "cuisine_type": establishment.cuisine_type,
            "opening_hours": establishment.opening_hours,
            "area": establishment.area,
            "availability_status": establishment.availability_status,

            # Évaluation
            "rating": establishment.rating,
            "reviews_count": establishment.reviews_count,

            # Dates
            "created_at": establishment.created_at,
            "updated_at": establishment.updated_at,
        }   
        
        
    # ---------------------------------------------------------
    # LECTURE PUBLIQUE
    # ---------------------------------------------------------

    async def list_establishments(
        self,
        db: AsyncSession,
        *,
        q: Optional[str] = None,
        category_id: Optional[UUID] = None,
        subcategory_id: Optional[UUID] = None,
        location_id: Optional[UUID] = None,
        amenity_ids: Optional[list[UUID]] = None,
        minimum_price: Optional[Decimal] = None,
        maximum_price: Optional[Decimal] = None,
        minimum_rating: Optional[Decimal] = None,
        sort: str = "newest",
        limit: int = 20,
        offset: int = 0,
        # Hébergement
        check_in: Optional[date] = None,
        check_out: Optional[date] = None,
        # Restaurant
        reservation_date: Optional[date] = None,
        arrival_time: Optional[time] = None,
        # Critère commun
        guests: Optional[int] = None,
        # Loisirs
        activity_type_id: Optional[UUID] = None,
        activity_date: Optional[date] = None,
        participants: Optional[int] = None,
    ) -> dict[str, Any]:

        # ---------------------------------------------------------
        # 1. VALIDATIONS
        # ---------------------------------------------------------

        if (
            minimum_price is not None
            and maximum_price is not None
            and minimum_price > maximum_price
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le prix minimum ne peut pas dépasser le prix maximum.",
            )

        if (check_in is None) != (check_out is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Les dates d'arrivée et de départ doivent être renseignées ensemble.",
            )

        if (
            check_in is not None
            and check_out is not None
            and check_out <= check_in
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La date de départ doit être postérieure à la date d'arrivée.",
            )

        if (reservation_date is None) != (arrival_time is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La date et l'heure d'arrivée au restaurant doivent être renseignées ensemble.",
            )

        if guests is not None and guests < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le nombre de personnes doit être supérieur ou égal à 1.",
            )

        if participants is not None and participants < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le nombre de participants doit être supérieur ou égal à 1.",
            )

        # ---------------------------------------------------------
        # 2. REQUÊTE DE BASE
        # ---------------------------------------------------------

        query = self._list_query()

        # ---------------------------------------------------------
        # 3. RECHERCHE TEXTUELLE
        # ---------------------------------------------------------

        if q:
            q = q.strip()

            if len(q) < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La recherche doit contenir au moins 2 caractères.",
                )

            pattern = f"%{q}%"

            query = query.where(
                or_(
                    Establishment.name.ilike(pattern),
                    Establishment.description.ilike(pattern),
                )
            )

        # ---------------------------------------------------------
        # 4. FILTRES EXISTANTS
        # ---------------------------------------------------------

        if category_id is not None:
            query = query.where(
                Establishment.category_id == category_id
            )

        if subcategory_id is not None:
            query = query.where(
                Establishment.subcategory_id == subcategory_id
            )

        if location_id is not None:
            query = query.where(
                Establishment.location_id == location_id
            )

        if amenity_ids:
            unique_amenity_ids = set(amenity_ids)

            query = query.where(
                Establishment.id.in_(
                    select(EstablishmentAmenity.establishment_id)
                    .where(
                        EstablishmentAmenity.amenity_id.in_(unique_amenity_ids)
                    )
                    .group_by(EstablishmentAmenity.establishment_id)
                    .having(
                        func.count(EstablishmentAmenity.amenity_id)
                        == len(unique_amenity_ids)
                    )
                )
            )

        if minimum_price is not None:
            query = query.where(
                Establishment.price >= minimum_price
            )

        if maximum_price is not None:
            query = query.where(
                Establishment.price <= maximum_price
            )

        if minimum_rating is not None:
            query = query.where(
                Establishment.rating >= minimum_rating
            )

        # ---------------------------------------------------------
        # 5. FILTRE PAR TYPE D'ACTIVITÉ
        # ---------------------------------------------------------

        # Le type d'activité correspond à la sous-catégorie.
        if activity_type_id is not None:
            query = query.where(
                Establishment.subcategory_id == activity_type_id
            )

        # ---------------------------------------------------------
        # 6. DISPONIBILITÉ DE L'HÉBERGEMENT
        # ---------------------------------------------------------

        if check_in is not None and check_out is not None:

            # Recherche d'une réservation active chevauchant le séjour.
            overlapping_reservation = (
                select(Reservation.id)
                .where(
                    Reservation.establishment_id == Establishment.id,
                    Reservation.status.in_(
                        self.ACTIVE_RESERVATION_STATUSES
                    ),
                    Reservation.start_date < check_out,
                    Reservation.end_date > check_in,
                )
                .exists()
            )

            # Une réservation chevauchante exclut l'établissement.
            query = query.where(~overlapping_reservation)

        # ---------------------------------------------------------
        # 7. CAPACITÉ POUR L'HÉBERGEMENT
        # ---------------------------------------------------------

        if guests is not None:
            query = query.where(
                or_(
                    Establishment.capacity.is_(None),
                    Establishment.capacity >= guests,
                )
            )

        # ---------------------------------------------------------
        # 8. RESTAURANT : CAPACITÉ AU CRÉNEAU DEMANDÉ
        # ---------------------------------------------------------

        if (
            reservation_date is not None
            and arrival_time is not None
            and guests is not None
        ):
            booked_people = (
                select(
                    func.coalesce(
                        func.sum(
                            Reservation.adults + Reservation.children
                        ),
                        0,
                    )
                )
                .where(
                    Reservation.establishment_id == Establishment.id,
                    Reservation.status.in_(
                        self.ACTIVE_RESERVATION_STATUSES
                    ),
                    Reservation.reservation_date == reservation_date,
                    Reservation.start_time <= arrival_time,
                    or_(
                        Reservation.end_time.is_(None),
                        Reservation.end_time > arrival_time,
                    ),
                )
                .correlate(Establishment)
                .scalar_subquery()
            )

            query = query.where(
                or_(
                    Establishment.capacity.is_(None),
                    Establishment.capacity - booked_people >= guests,
                )
            )

        # ---------------------------------------------------------
        # 9. LOISIRS : CAPACITÉ À LA DATE DEMANDÉE
        # ---------------------------------------------------------

        if activity_date is not None and participants is not None:

            booked_participants = (
                select(
                    func.coalesce(
                        func.sum(
                            Reservation.adults + Reservation.children
                        ),
                        0,
                    )
                )
                .where(
                    Reservation.establishment_id == Establishment.id,
                    Reservation.status.in_(
                        self.ACTIVE_RESERVATION_STATUSES
                    ),
                    or_(
                        Reservation.reservation_date == activity_date,
                        and_(
                            Reservation.reservation_date.is_(None),
                            Reservation.start_date == activity_date,
                        ),
                    ),
                )
                .correlate(Establishment)
                .scalar_subquery()
            )

            query = query.where(
                or_(
                    Establishment.capacity.is_(None),
                    Establishment.capacity - booked_participants
                    >= participants,
                )
            )

        # ---------------------------------------------------------
        # 10. TRI
        # ---------------------------------------------------------

        order_by = {
            "newest": Establishment.created_at.desc(),
            "rating": Establishment.rating.desc(),
            "price_asc": Establishment.price.asc(),
            "price_desc": Establishment.price.desc(),
            "name": Establishment.name.asc(),
        }.get(sort, Establishment.created_at.desc())

        query = query.order_by(order_by)

        # ---------------------------------------------------------
        # 11. TOTAL AVANT PAGINATION
        # ---------------------------------------------------------

        count_query = select(func.count()).select_from(
            query.order_by(None).subquery()
        )

        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # ---------------------------------------------------------
        # 12. RÉSULTATS PAGINÉS
        # ---------------------------------------------------------

        result = await db.execute(
            query.offset(offset).limit(limit)
        )

        establishments = result.scalars().unique().all()

        return {
            "items": [
                self.serialize_list_item(item)
                for item in establishments
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def list_popular_establishments(
        self,
        db: AsyncSession,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Retourne les établissements publics les plus populaires.

        Classement :
        1. Nombre d'avis décroissant.
        2. Note moyenne décroissante.
        3. Date de création décroissante.
        """

        query = (
            self._list_query()
            .order_by(
                func.coalesce(
                    Establishment.reviews_count, 0
                ).desc(),
                func.coalesce(
                    Establishment.rating, 0
                ).desc(),
                Establishment.created_at.desc(),
            )
        )

        # Compter uniquement les établissements publiés.
        count_query = select(func.count()).select_from(
            query.order_by(None).subquery()
        )

        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Récupérer les établissements populaires.
        result = await db.execute(
            query.offset(offset).limit(limit)
        )

        establishments = result.scalars().unique().all()

        return {
            "items": [
                self.serialize_list_item(establishment)
                for establishment in establishments
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def list_nearby_establishments(
        self,
        db: AsyncSession,
        *,
        latitude: float,
        longitude: float,
        radius_km: float = 10,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Retourne les établissements publiés situés dans un rayon donné,
        classés du plus proche au plus éloigné.
        """

        # Rayon moyen de la Terre en kilomètres.
        earth_radius_km = 6371.0

        # Formule de Haversine, sous forme SQL.
        lat1 = func.radians(latitude)
        lon1 = func.radians(longitude)
        lat2 = func.radians(Establishment.latitude)
        lon2 = func.radians(Establishment.longitude)

        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1

        haversine = (
            func.pow(func.sin(delta_lat / 2), 2)
            + func.cos(lat1)
            * func.cos(lat2)
            * func.pow(func.sin(delta_lon / 2), 2)
        )

        # Protection contre les imprécisions numériques.
        safe_haversine = func.least(
            1.0,
            func.greatest(0.0, haversine),
        )

        distance_km = (
            2
            * earth_radius_km
            * func.asin(func.sqrt(safe_haversine))
        )

        query = (
            self._list_query()
            .where(
                Establishment.latitude.is_not(None),
                Establishment.longitude.is_not(None),
                distance_km <= radius_km,
            )
            .order_by(
                distance_km.asc(),
                Establishment.id.asc(),
            )
        )

        # Nombre total de résultats correspondant au rayon.
        count_query = select(func.count()).select_from(
            query.order_by(None).subquery()
        )

        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        # Résultats paginés.
        result = await db.execute(
            query.offset(offset).limit(limit)
        )

        establishments = result.scalars().unique().all()

        return {
            "items": [
                self.serialize_list_item(establishment)
                for establishment in establishments
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_establishment_by_slug(
        self,
        db: AsyncSession,
        slug: str,
    ) -> Establishment:
            result = await db.execute(
            self._detail_query().where(
                    func.lower(Establishment.slug) == slug.lower()
                )
            )
            establishment = result.scalars().unique().first()

            if establishment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Établissement introuvable.",
                )

            return establishment

    async def get_establishment_by_id(
        self,
        db: AsyncSession,
        establishment_id: UUID,
    ) -> Establishment:
        result = await db.execute(
            self._list_query().where(
                Establishment.id == establishment_id
            )
        )
        establishment = result.scalars().unique().first()

        if establishment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Établissement introuvable.",
            )

        return establishment

    async def list_similar(
        self,
        db: AsyncSession,
        establishment_id: UUID,
        *,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        establishment = await self.get_establishment_by_id(
            db, establishment_id
        )

        result = await db.execute(
            self._list_query().where(
                Establishment.id != establishment.id,
                or_(
                    Establishment.category_id
                    == establishment.category_id,
                    Establishment.location_id
                    == establishment.location_id,
                ),
            )
            .order_by(Establishment.rating.desc())
            .limit(limit)
        )

        return [
            self.serialize_list_item(item)
            for item in result.scalars().unique().all()
        ]

    async def list_reviews(
        self,
        db: AsyncSession,
        establishment_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        await self.get_establishment_by_id(db, establishment_id)

        filters = [
            Review.establishment_id == establishment_id,
            Review.is_approved.is_(True),
            Review.id.isnot(None),
        ]

        count_result = await db.execute(
            select(func.count(Review.id)).where(*filters)
        )
        total = count_result.scalar_one()

        avg_result = await db.execute(
            select(func.avg(Review.rating)).where(*filters)
        )
        average_rating = avg_result.scalar_one() or 0

        result = await db.execute(
            select(Review)
            .options(
                selectinload(Review.user).selectinload(User.profile)
            )
            .where(*filters)
            .order_by(Review.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        items = []
        for review in result.scalars().unique().all():
            profile = (
                getattr(review.user, "profile", None)
                if review.user
                else None
            )
            first_name = profile.firstName if profile else ""
            last_name = profile.lastName if profile else ""

            items.append(
                {
                    "id": review.id,
                    "rating": review.rating,
                    "comment": getattr(review, "comment", None),
                    "created_at": review.created_at,
                    "author_name": (
                        f"{first_name} {last_name}".strip()
                        or "Client BestRev"
                    ),
                    "author_avatar": profile.img if profile else None,
                }
            )

        return {
            "items": items,
            "total": total,
            "average_rating": average_rating,
            "limit": limit,
            "offset": offset,
        }

    # ---------------------------------------------------------
    # ADMINISTRATION
    # ---------------------------------------------------------

    async def _get_admin_establishment(
        self,
        establishment_id: UUID,
        db: AsyncSession,
        *,
        for_update: bool = False,
    ) -> Establishment:
        query = self._detail_query(include_all_statuses=True).where(
            Establishment.id == establishment_id
        )

        if for_update:
            query = query.with_for_update()

        result = await db.execute(query)
        establishment = result.scalars().unique().first()

        if establishment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Établissement introuvable.",
            )

        return establishment

    async def list_admin_establishments(
        self,
        db: AsyncSession,
        *,
        q: Optional[str] = None,
        category_id: Optional[UUID] = None,
        status_filter: Optional[str] = None,
        sort: str = "newest",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = self._list_query(include_all_statuses=True)

        if q:
            query = query.where(
                Establishment.name.ilike(f"%{q.strip()}%")
            )

        if category_id:
            query = query.where(
                Establishment.category_id == category_id
            )

        if status_filter:
            try:
                enum_status = EstablishmentStatus(status_filter)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Statut d'établissement invalide.",
                ) from exc

            query = query.where(Establishment.status == enum_status)

        order_by = {
            "newest": Establishment.created_at.desc(),
            "rating": Establishment.rating.desc(),
            "price_asc": Establishment.price.asc(),
            "price_desc": Establishment.price.desc(),
            "name": Establishment.name.asc(),
        }.get(sort, Establishment.created_at.desc())

        query = query.order_by(order_by)

        count_query = select(func.count()).select_from(
            query.order_by(None).subquery()
        )
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        result = await db.execute(
            query.offset(offset).limit(limit)
        )

        return {
            "items": [
                self.serialize_list_item(item)
                for item in result.scalars().unique().all()
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower())
        return slug.strip("-")

    async def _ensure_slug(
        self,
        slug: str,
        db: AsyncSession,
        *,
        exclude_id: Optional[UUID] = None,
    ) -> None:
        if not slug or not slug.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le slug est obligatoire.",
            )

        query = select(Establishment.id).where(
            func.lower(Establishment.slug) == slug.lower()
        )

        if exclude_id:
            query = query.where(Establishment.id != exclude_id)

        result = await db.execute(query.limit(1))

        if result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce slug est déjà utilisé.",
            )

    async def _validate_references(
        self,
        category_id: UUID,
        subcategory_id: Optional[UUID],
        location_id: UUID,
        db: AsyncSession,
    ) -> None:
        category_result = await db.execute(
            select(Category.id).where(Category.id == category_id)
        )
        if not category_result.first():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Catégorie introuvable.",
            )

        location_result = await db.execute(
            select(Location.id).where(Location.id == location_id)
        )
        if not location_result.first():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Localisation introuvable.",
            )

        if subcategory_id:
            subcategory_result = await db.execute(
                select(SubCategory).where(
                    SubCategory.id == subcategory_id,
                    SubCategory.category_id == category_id,
                )
            )
            if not subcategory_result.first():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La sous-catégorie ne correspond pas à la catégorie.",
                )

    @staticmethod
    def _audit(
        db: AsyncSession,
        actor: User,
        action: str,
        establishment: Establishment,
        request: Request,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        db.add(
            ActivityLog(
                user_id=actor.id,
                action=action,
                entity_type="establishment",
                entity_id=establishment.id,
                ip_address=(
                    request.client.host if request.client else None
                ),
                user_agent=request.headers.get("user-agent", "")[:1000]
                or None,
                metadata_json=metadata or {},
            )
        )

    # ---------------------------------------------------------
    # SUPPRESSION PHYSIQUE SANS CASCADE DESTRUCTIVE
    # ---------------------------------------------------------

    async def delete_establishment(
        self,
        establishment_id: UUID,
        db: AsyncSession,
        actor: User,
        request: Request,
    ) -> dict[str, str]:
        """
        Supprime physiquement un établissement uniquement
        lorsqu'aucune dépendance bloquante n'existe.
        Empêche le lazy loading implicite avec AsyncSession.
        """

        establishment = await self._get_admin_establishment(
            establishment_id,
            db,
            for_update=True,
        )

        # 1. Vérifier les réservations
        reservation_result = await db.execute(
            select(Reservation.id)
            .where(
                Reservation.establishment_id == establishment.id
            )
            .limit(1)
        )

        if reservation_result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Suppression refusée : cet établissement "
                    "possède des réservations. "
                    "Suspendez-le plutôt pour préserver l'historique."
                ),
            )

        # 2. Vérifier les avis
        review_result = await db.execute(
            select(Review.id)
            .where(
                Review.establishment_id == establishment.id
            )
            .limit(1)
        )

        if review_result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Suppression refusée : cet établissement "
                    "possède des avis. "
                    "Conservez ou archivez ces données."
                ),
            )

        # 3. Vérifier les relations déclarées dans le modèle
        relationship_names = (
            "photos",
            "amenity_links",
            "payment_condition_links",
            "favorites",
            "validation_documents",
        )

        dependencies = {}

        # Relations réellement déclarées sur Establishment
        declared_relationships = {
            relationship.key
            for relationship in
            Establishment.__mapper__.relationships
        }

        for relationship_name in relationship_names:

            if relationship_name not in declared_relationships:
                continue

            # Chargement explicite de la relation.
            # Évite le lazy loading synchrone (MissingGreenlet).
            await db.refresh(
                establishment,
                attribute_names=[relationship_name],
            )

            related_items = getattr(
                establishment,
                relationship_name,
                None,
            )

            if related_items is None:
                continue

            # Collection ou relation individuelle
            if isinstance(related_items, (list, tuple, set)):
                has_dependency = bool(related_items)
            else:
                has_dependency = True

            if has_dependency:
                dependencies[relationship_name] = True

        # 4. Refuser la suppression si dépendances présentes
        if dependencies:
            blocking = ", ".join(dependencies.keys())

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Suppression refusée : dépendances présentes "
                    f"({blocking})."
                ),
            )

        # 5. Journaliser la suppression
        db.add(
            ActivityLog(
                user_id=actor.id,
                action="ADMIN_ESTABLISHMENT_DELETED",
                entity_type="establishment",
                entity_id=establishment.id,
                ip_address=(
                    request.client.host
                    if request.client
                    else None
                ),
                user_agent=(
                    request.headers.get("user-agent", "")[:1000]
                    or None
                ),
                metadata_json={},
            )
        )

        # 6. Supprimer physiquement l'établissement
        try:
            await db.delete(establishment)
            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Suppression refusée par la base de données : "
                    "une autre dépendance référence cet établissement."
                ),
            ) from exc

        except Exception:
            await db.rollback()
            raise

        return {
            "message": "Établissement supprimé définitivement."
        }


establishment_service = EstablishmentService()