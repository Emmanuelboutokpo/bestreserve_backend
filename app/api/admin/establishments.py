from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import Establishment, User
from app.models.enums import AvailabilityStatus, EstablishmentStatus
from app.schemas.establishment import (
    EstablishmentAdminPublic,
    EstablishmentAvailabilityPatch,
    EstablishmentCreate,
    EstablishmentPatch,
    EstablishmentStatusPatch,
    EstablishmentAdminDetailPublic
)

from app.schemas.establishment import EstablishmentPublic, EstablishmentPage
from app.services.establishment import establishment_service


admin_establishments_router = APIRouter(
    prefix="/admin/establishments",
    tags=["Administration des établissements"],
    dependencies=[Depends(require_admin)],
)


@admin_establishments_router.get(
    "",
    response_model=EstablishmentPage,
    summary="Liste administrative",
)
async def list_establishments_admin(
    q: Optional[str] = Query(None, min_length=2, max_length=200),
    category_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    sort: Literal[
        "newest", "rating", "price_asc", "price_desc", "name"
    ] = "newest",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    return await establishment_service.list_admin_establishments(
        db,
        q=q,
        category_id=category_id,
        status_filter=status_filter,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@admin_establishments_router.get(
    "/{establishment_id}",
    response_model=EstablishmentAdminDetailPublic,
    summary="Détail administratif",
)
async def get_establishment_admin(
    establishment_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    establishment = await establishment_service._get_admin_establishment(
        establishment_id,
        db,
    )
    data = establishment_service.serialize_detail(establishment)
    data["status"] = establishment.status
    return data


@admin_establishments_router.post(
    "",
    response_model=EstablishmentAdminPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un établissement",
)
async def create_establishment(
    data: EstablishmentCreate,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    await establishment_service._validate_references(
        data.category_id,
        data.subcategory_id,
        data.location_id,
        db,
    )

    payload = data.model_dump()
    supplied_slug = payload.pop("slug", None)
    slug = (
        establishment_service._slugify(payload["name"])
        if not supplied_slug
        else establishment_service._slugify(supplied_slug)
    )

    await establishment_service._ensure_slug(slug, db)

    establishment = Establishment(
        **payload,
        slug=slug,
        owner_id=actor.id,
        created_by=actor.id,
        updated_by=actor.id,
        status=EstablishmentStatus.PUBLIE,
        availability_status=AvailabilityStatus.AVAILABLE,
    )

    db.add(establishment)
    await db.flush()

    establishment_service._audit(
        db,
        actor,
        "ADMIN_ESTABLISHMENT_CREATED",
        establishment,
        request,
        metadata={"slug": slug},
    )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le slug ou une référence d'établissement est déjà utilisé.",
        ) from exc

    await db.refresh(establishment)
    return establishment


@admin_establishments_router.patch(
    "/{establishment_id}",
    response_model=EstablishmentAdminPublic,
    summary="Modifier un établissement",
)
async def update_establishment(
    establishment_id: UUID,
    data: EstablishmentPatch,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    establishment = await establishment_service._get_admin_establishment(
        establishment_id,
        db,
        for_update=True,
    )

    changes = data.model_dump(exclude_unset=True)

    category_id = changes.get("category_id", establishment.category_id)
    subcategory_id = changes.get(
        "subcategory_id", establishment.subcategory_id
    )
    location_id = changes.get("location_id", establishment.location_id)

    if (
        "category_id" in changes
        and category_id != establishment.category_id
        and "subcategory_id" not in changes
    ):
        subcategory_id = None
        changes["subcategory_id"] = None

    await establishment_service._validate_references(
        category_id,
        subcategory_id,
        location_id,
        db,
    )

    if "slug" in changes:
        changes["slug"] = establishment_service._slugify(changes["slug"])
        await establishment_service._ensure_slug(
            changes["slug"],
            db,
            exclude_id=establishment.id,
        )

    for field, value in changes.items():
        setattr(establishment, field, value)

    establishment.updated_by = actor.id

    establishment_service._audit(
        db,
        actor,
        "ADMIN_ESTABLISHMENT_UPDATED",
        establishment,
        request,
        metadata={"fields": sorted(changes)},
    )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le slug ou une référence d'établissement est déjà utilisé.",
        ) from exc

    await db.refresh(establishment)
    return establishment


@admin_establishments_router.delete(
    "/{establishment_id}",
    summary="Supprimer physiquement un établissement",
)
async def delete_establishment(
    establishment_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    return await establishment_service.delete_establishment(
        establishment_id,
        db,
        actor,
        request,
    )


@admin_establishments_router.patch(
    "/{establishment_id}/status",
    response_model=EstablishmentAdminPublic,
    summary="Modifier le statut",
)
async def update_establishment_status(
    establishment_id: UUID,
    data: EstablishmentStatusPatch,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    establishment = await establishment_service._get_admin_establishment(
        establishment_id,
        db,
        for_update=True,
    )

    if data.status == EstablishmentStatus.PUBLIE:
        await establishment_service._validate_references(
            establishment.category_id,
            establishment.subcategory_id,
            establishment.location_id,
            db,
        )

        if not establishment.name.strip() or not establishment.address.strip():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Le nom et l'adresse sont requis pour publier.",
            )

    establishment.status = data.status
    establishment.updated_by = actor.id

    establishment_service._audit(
        db,
        actor,
        "ADMIN_ESTABLISHMENT_STATUS_UPDATED",
        establishment,
        request,
        metadata={"status": data.status.value},
    )

    await db.commit()
    await db.refresh(establishment)
    return establishment


@admin_establishments_router.patch(
    "/{establishment_id}/availability",
    response_model=EstablishmentAdminPublic,
    summary="Modifier la disponibilité",
)
async def update_establishment_availability(
    establishment_id: UUID,
    data: EstablishmentAvailabilityPatch,
    request: Request,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    establishment = await establishment_service._get_admin_establishment(
        establishment_id,
        db,
        for_update=True,
    )

    establishment.availability_status = data.availability_status
    establishment.updated_by = actor.id

    establishment_service._audit(
        db,
        actor,
        "ADMIN_ESTABLISHMENT_AVAILABILITY_UPDATED",
        establishment,
        request,
        metadata={
            "availability_status": data.availability_status.value
        },
    )

    await db.commit()
    await db.refresh(establishment)
    return establishment