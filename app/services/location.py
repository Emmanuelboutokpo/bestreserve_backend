from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import ActivityLog, Establishment, Location
from app.models.enums import LocationType
from app.schemas.location import LocationCreate, LocationImportItem, LocationPatch


class LocationService:
    """Logique métier et accès aux données pour les lieux géographiques."""

    MAX_TREE_DEPTH = 12
    MAX_TREE_NODES = 1000
    MAX_EXPORT_ROWS = 10000

    PARENT_TYPES = {
        LocationType.REGION: {LocationType.COUNTRY},
        LocationType.CITY: {LocationType.COUNTRY, LocationType.REGION},
        LocationType.DISTRICT: {LocationType.CITY},
        LocationType.NEIGHBORHOOD: {
            LocationType.CITY,
            LocationType.DISTRICT,
        },
    }

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------

    def public_location(self, location: Location) -> dict[str, Any]:
        try:
            metadata = (
                json.loads(location.metadata_json)
                if location.metadata_json
                else None
            )
        except (TypeError, json.JSONDecodeError):
            metadata = None

        return {
            "id": location.id,
            "name": location.name,
            "type": location.type,
            "parent_id": location.parent_id,
            "country_code": location.country_code,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": location.timezone,
            "population": location.population,
            "metadata_json": metadata,
            "is_active": location.is_active,
            "created_at": location.created_at,
            "updated_at": location.updated_at,
        }

    def admin_location(self, location: Location) -> dict[str, Any]:
        return self.public_location(location)

    # ------------------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------------------

    def normalize_code(self, code: str) -> str:
        normalized = code.strip().upper()

        if (
            len(normalized) != 2
            or not normalized.isascii()
            or not normalized.isalpha()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le code pays doit contenir deux lettres ASCII.",
            )

        return normalized

    def escape_like(self, value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

    def json_metadata(self, value: dict[str, Any] | None) -> str | None:
        if value is None:
            return None

        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        if len(encoded) > 5000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Les métadonnées ne peuvent pas dépasser 5000 caractères.",
            )

        return encoded

    # ------------------------------------------------------------------
    # GET LOCATIONS
    # ------------------------------------------------------------------

    async def get_public_location(
        self,
        location_id: UUID,
        session: AsyncSession,
    ) -> Location:
        statement = select(Location).where(
            Location.id == location_id,
            Location.is_active.is_(True),
        )
        result = await session.execute(statement)
        location = result.scalars().first()

        if location is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lieu introuvable.",
            )

        return location

    async def get_admin_location(
        self,
        location_id: UUID,
        session: AsyncSession,
        *,
        for_update: bool = False,
    ) -> Location:
        statement = select(Location).where(Location.id == location_id)

        if for_update:
            statement = statement.with_for_update()

        result = await session.execute(statement)
        location = result.scalars().first()

        if location is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lieu introuvable.",
            )

        return location

    async def get_country(
        self,
        code: str,
        session: AsyncSession,
    ) -> Location:
        normalized = self.normalize_code(code)

        statement = select(Location).where(
            Location.country_code == normalized,
            Location.type == LocationType.COUNTRY,
            Location.parent_id.is_(None),
            Location.is_active.is_(True),
        )
        result = await session.execute(statement)
        country = result.scalars().first()

        if country is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pays introuvable.",
            )

        return country

    # ------------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------------

    async def ensure_unique_country_code(
        self,
        location_type: LocationType,
        country_code: str,
        session: AsyncSession,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        """Un code pays doit être unique parmi les pays racines."""

        if location_type != LocationType.COUNTRY:
            return

        normalized_code = self.normalize_code(country_code)
        statement = select(Location.id).where(
            Location.type == LocationType.COUNTRY,
            Location.country_code == normalized_code,
            Location.parent_id.is_(None),
        )

        if exclude_id is not None:
            statement = statement.where(Location.id != exclude_id)

        result = await session.execute(statement)

        if result.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un pays utilisant ce code existe déjà.",
            )

    async def validate_parent(
        self,
        location_type: LocationType,
        parent_id: UUID | None,
        country_code: str,
        session: AsyncSession,
        *,
        current_id: UUID | None = None,
    ) -> Location | None:
        """Valide le parent, son type, son pays et l'absence de cycle."""

        if location_type == LocationType.COUNTRY:
            if parent_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Un pays ne peut pas avoir de parent.",
                )
            return None

        if parent_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Un lieu autre qu'un pays doit avoir un parent.",
            )

        allowed_parent_types = self.PARENT_TYPES.get(location_type)
        if allowed_parent_types is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Type de lieu invalide.",
            )

        parent = await self.get_admin_location(
            parent_id,
            session,
            for_update=True,
        )

        if not parent.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un lieu ne peut pas être rattaché à un parent inactif.",
            )

        if parent.type not in allowed_parent_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le type du parent ne convient pas à ce lieu.",
            )

        normalized_code = self.normalize_code(country_code)
        if parent.country_code != normalized_code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le lieu et son parent doivent appartenir au même pays.",
            )

        # Remonte la chaîne des parents pour détecter les cycles.
        visited: set[UUID] = set()
        ancestor_id: UUID | None = parent.id

        while ancestor_id is not None:
            if current_id is not None and ancestor_id == current_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cette modification créerait une boucle géographique.",
                )

            if ancestor_id in visited:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La hiérarchie géographique contient déjà une boucle.",
                )

            visited.add(ancestor_id)
            ancestor = await session.get(Location, ancestor_id)
            ancestor_id = ancestor.parent_id if ancestor is not None else None

        return parent

    async def check_children_after_update(
        self,
        location: Location,
        new_type: LocationType,
        new_country_code: str,
        is_active: bool,
        session: AsyncSession,
    ) -> None:
        """Empêche une modification qui invaliderait les lieux enfants."""

        result = await session.execute(
            select(Location).where(Location.parent_id == location.id)
        )
        children = result.scalars().all()

        for child in children:
            if not is_active and child.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Désactivez d'abord les lieux enfants.",
                )

            if child.country_code != new_country_code:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Le code pays ne peut pas être modifié tant que "
                        "des enfants y sont rattachés."
                    ),
                )

            allowed_types = self.PARENT_TYPES.get(child.type, set())
            if new_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Le type ne peut pas être modifié car il invaliderait "
                        "un lieu enfant."
                    ),
                )

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------

    def audit_location(
        self,
        session: AsyncSession,
        actor_id: UUID,
        location: Location,
        action: str,
        request: Request,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Ajoute une entrée d'audit à la session courante."""

        session.add(
            ActivityLog(
                user_id=actor_id,
                action=action,
                entity_type="location",
                entity_id=location.id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:1000] or None,
                metadata_json=metadata or {},
            )
        )

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    async def create_location(
        self,
        data: LocationCreate | LocationImportItem,
        session: AsyncSession,
        *,
        item_id: UUID | None = None,
    ) -> Location:
        values = data.model_dump(
            exclude={"id"},
            exclude_unset=True,
        )

        if "country_code" not in values or "type" not in values or "name" not in values:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le nom, le type et le code pays sont obligatoires.",
            )

        values["country_code"] = self.normalize_code(values["country_code"])
        values["metadata_json"] = self.json_metadata(
            values.get("metadata_json")
        )

        await self.validate_parent(
            values["type"],
            values.get("parent_id"),
            values["country_code"],
            session,
        )

        await self.ensure_unique_country_code(
            values["type"],
            values["country_code"],
            session,
        )

        if item_id is not None:
            existing = await session.get(Location, item_id)
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="L'identifiant fourni existe déjà.",
                )

        location = (
            Location(id=item_id, **values)
            if item_id is not None
            else Location(**values)
        )

        session.add(location)
        await session.flush()
        return location

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    async def update_location(
        self,
        location_id: UUID,
        data: LocationPatch,
        session: AsyncSession,
    ) -> Location:
        location = await self.get_admin_location(
            location_id,
            session,
            for_update=True,
        )

        values = data.model_dump(exclude_unset=True)

        new_type = values.get("type", location.type)
        new_country_code = self.normalize_code(
            values.get("country_code", location.country_code)
        )
        new_parent_id = values.get("parent_id", location.parent_id)
        new_is_active = values.get("is_active", location.is_active)

        # Valide le parent même si le type ou le parent n'a pas changé,
        # afin de détecter les données incohérentes avant la mise à jour.
        await self.validate_parent(
            new_type,
            new_parent_id,
            new_country_code,
            session,
            current_id=location.id,
        )

        await self.ensure_unique_country_code(
            new_type,
            new_country_code,
            session,
            exclude_id=location.id,
        )

        await self.check_children_after_update(
            location,
            new_type,
            new_country_code,
            new_is_active,
            session,
        )

        if "metadata_json" in values:
            values["metadata_json"] = self.json_metadata(
                values["metadata_json"]
            )

        if "country_code" in values:
            values["country_code"] = new_country_code

        for key, value in values.items():
            setattr(location, key, value)

        await session.flush()
        await session.refresh(location)
        return location

    # ------------------------------------------------------------------
    # DELETE (physical deletion, without cascading)
    # ------------------------------------------------------------------

    async def delete_location(
        self,
        location_id: UUID,
        session: AsyncSession,
    ) -> Location:
        location = await self.get_admin_location(
            location_id,
            session,
            for_update=True,
        )

        child_result = await session.execute(
            select(Location.id)
            .where(Location.parent_id == location.id)
            .limit(1)
        )

        establishment_result = await session.execute(
            select(Establishment.id)
            .where(Establishment.location_id == location.id)
            .limit(1)
        )

        if child_result.first() or establishment_result.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Ce lieu possède des sous-lieux ou des établissements. "
                    "Désassociez-les avant de le supprimer."
                ),
            )

        await session.delete(location)
        await session.flush()
        return location


location_service = LocationService()
