
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import Establishment, Location
from app.schemas.location import (
    LocationCreate,
    LocationAdminPublic,
    LocationPatch,
)
from app.services.location import location_service as service


admin_locations_router = APIRouter(
    prefix="/locations",
    tags=["Administration géographique"],
    dependencies=[Depends(require_admin)],
)


@admin_locations_router.post(
    "",
    response_model=LocationAdminPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_location(
    data: LocationCreate,
    request: Request,
    actor=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        location = await service.create_location(data, session)

        service.audit_location(
            session,
            actor.id,
            location,
            "ADMIN_LOCATION_CREATED",
            request,
        )

        await session.commit()
        await session.refresh(location)

    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce slug ou cet identifiant existe déjà.",
        ) from exc

    return service.admin_location(location)


@admin_locations_router.patch(
    "/{location_id}",
    response_model=LocationAdminPublic,
)
async def update_location(
    location_id: UUID,
    data: LocationPatch,
    request: Request,
    actor=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        location = await service.get_admin_location(
            location_id,
            session,
            for_update=True,
        )

        changes = data.model_dump(exclude_unset=True)

        if changes.get("country_code") is not None:
            changes["country_code"] = service.normalize_code(
                changes["country_code"]
            )

        if changes.get("slug") is not None:
            await service.ensure_unique_slug(
                changes["slug"],
                session,
                exclude_id=location.id,
            )

        if "metadata_json" in changes:
            changes["metadata_json"] = service.json_metadata(
                changes["metadata_json"]
            )

        new_type = changes.get("type", location.type)
        new_parent_id = changes.get("parent_id", location.parent_id)
        new_country_code = changes.get(
            "country_code",
            location.country_code,
        )
        new_active = changes.get("is_active", location.is_active)

        await service.ensure_unique_country_code(
            new_type,
            new_country_code,
            session,
            exclude_id=location.id,
        )

        await service.validate_parent(
            new_type,
            new_parent_id,
            new_country_code,
            session,
            current_id=location.id,
        )

        await service.check_children_after_update(
            location,
            new_type,
            new_country_code,
            new_active,
            session,
        )

        for field, value in changes.items():
            setattr(location, field, value)

        service.audit_location(
            session,
            actor.id,
            location,
            "ADMIN_LOCATION_UPDATED",
            request,
            metadata={"fields": sorted(changes)},
        )

        await session.commit()
        await session.refresh(location)

    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une contrainte d'unicité est violée.",
        ) from exc

    return service.admin_location(location)


@admin_locations_router.delete("/{location_id}")
async def delete_location(
    location_id: UUID,
    request: Request,
    actor=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        location = await service.get_admin_location(
            location_id,
            session,
            for_update=True,
        )

        # Refuser la suppression si des sous-lieux existent.
        child_result = await session.execute(
            select(Location.id)
            .where(Location.parent_id == location.id)
            .limit(1)
        )

        # Refuser la suppression si des établissements sont associés.
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

        service.audit_location(
            session,
            actor.id,
            location,
            "ADMIN_LOCATION_DELETED",
            request,
        )

        # Suppression physique du seul lieu ciblé.
        await session.delete(location)
        await session.commit()

    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Impossible de supprimer ce lieu en raison "
                "d'une dépendance en base de données."
            ),
        ) from exc

    return {"message": "Lieu supprimé."}
