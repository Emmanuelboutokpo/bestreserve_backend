from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import Establishment, User
from app.models.enums import AvailabilityStatus, EstablishmentStatus
from app.schemas.establishment import (
    EstablishmentAdminDetailPublic,
    EstablishmentAdminPublic,
    EstablishmentAvailabilityPatch,
    EstablishmentCreate,
    EstablishmentPage,
    EstablishmentPatch,
)
from app.services.establishment import establishment_service
from app.services.owner_scope import (
    validate_admin_managed_category,
)


admin_managed_establishments_router = APIRouter(
    prefix="/admin/managed-establishments",
    tags=["Administration - Restaurants et loisirs"],
    dependencies=[Depends(require_admin)],
)


async def _get_managed_establishment(
    establishment_id: UUID,
    session: AsyncSession,
    *,
    for_update: bool = False,
) -> Establishment:
    establishment = await establishment_service._get_admin_establishment(
        establishment_id,
        session,
        for_update=for_update,
    )
    await validate_admin_managed_category(
        establishment.category_id,
        session,
    )
    return establishment


@admin_managed_establishments_router.get(
    "",
    response_model=EstablishmentPage,
    summary="Lister les restaurants et lieux de loisirs",
)
async def list_managed_establishments(
    category_type: Literal["restaurant", "loisir"] | None = None,
    q: str | None = Query(default=None, min_length=2, max_length=200),
    category_id: UUID | None = None,
    status_filter: EstablishmentStatus | None = Query(
        default=None,
        alias="status",
    ),
    sort: Literal[
        "newest", "rating", "price_asc", "price_desc", "name"
    ] = "newest",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await establishment_service.list_admin_establishments(
        session,
        q=q,
        category_id=category_id,
        status_filter=status_filter,
        sort=sort,
        limit=limit,
        offset=offset,
        managed_category=category_type or "all",
    )


@admin_managed_establishments_router.post(
    "",
    response_model=EstablishmentAdminPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un restaurant ou un lieu de loisirs",
)
async def create_managed_establishment(
    data: EstablishmentCreate,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await validate_admin_managed_category(data.category_id, session)
    await establishment_service._validate_references(
        data.category_id,
        data.subcategory_id,
        data.location_id,
        session,
    )

    payload = data.model_dump()
    supplied_slug = payload.pop("slug", None)
    slug = (
        establishment_service._slugify(payload["name"])
        if not supplied_slug
        else establishment_service._slugify(supplied_slug)
    )
    await establishment_service._ensure_slug(slug, session)

    establishment = Establishment(
        **payload,
        slug=slug,
        owner_id=actor.id,
        created_by=actor.id,
        updated_by=actor.id,
        status=EstablishmentStatus.PUBLIE,
        availability_status=AvailabilityStatus.AVAILABLE,
    )
    session.add(establishment)
    await session.flush()
    establishment_service._audit(
        session,
        actor,
        "ADMIN_MANAGED_ESTABLISHMENT_CREATED",
        establishment,
        request,
        metadata={"slug": slug},
    )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le slug ou une référence d'établissement est déjà utilisé.",
        ) from exc

    await session.refresh(establishment)
    return establishment


@admin_managed_establishments_router.get(
    "/{establishment_id}",
    response_model=EstablishmentAdminDetailPublic,
    summary="Consulter un restaurant ou un lieu de loisirs",
)
async def get_managed_establishment(
    establishment_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    establishment = await _get_managed_establishment(
        establishment_id,
        session,
    )
    data = establishment_service.serialize_detail(
        establishment,
        location_access=True,
    )
    data["status"] = establishment.status
    return data


@admin_managed_establishments_router.patch(
    "/{establishment_id}",
    response_model=EstablishmentAdminPublic,
    summary="Modifier un restaurant ou un lieu de loisirs",
)
async def update_managed_establishment(
    establishment_id: UUID,
    data: EstablishmentPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    establishment = await _get_managed_establishment(
        establishment_id,
        session,
        for_update=True,
    )
    changes = data.model_dump(exclude_unset=True)
    category_id = changes.get("category_id", establishment.category_id)
    subcategory_id = changes.get(
        "subcategory_id",
        establishment.subcategory_id,
    )
    location_id = changes.get("location_id", establishment.location_id)

    await validate_admin_managed_category(category_id, session)

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
        session,
    )

    if "slug" in changes:
        changes["slug"] = establishment_service._slugify(changes["slug"])
        await establishment_service._ensure_slug(
            changes["slug"],
            session,
            exclude_id=establishment.id,
        )

    for field, value in changes.items():
        setattr(establishment, field, value)
    establishment.updated_by = actor.id
    establishment_service._audit(
        session,
        actor,
        "ADMIN_MANAGED_ESTABLISHMENT_UPDATED",
        establishment,
        request,
        metadata={"fields": sorted(changes)},
    )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le slug ou une référence d'établissement est déjà utilisé.",
        ) from exc

    await session.refresh(establishment)
    return establishment


@admin_managed_establishments_router.patch(
    "/{establishment_id}/availability",
    response_model=EstablishmentAdminPublic,
    summary="Modifier la disponibilité",
)
async def update_managed_establishment_availability(
    establishment_id: UUID,
    data: EstablishmentAvailabilityPatch,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    establishment = await _get_managed_establishment(
        establishment_id,
        session,
        for_update=True,
    )
    establishment.availability_status = data.availability_status
    establishment.updated_by = actor.id
    establishment_service._audit(
        session,
        actor,
        "ADMIN_MANAGED_ESTABLISHMENT_AVAILABILITY_UPDATED",
        establishment,
        request,
        metadata={"availability_status": data.availability_status.value},
    )
    await session.commit()
    await session.refresh(establishment)
    return establishment


@admin_managed_establishments_router.delete(
    "/{establishment_id}",
    summary="Supprimer un restaurant ou un lieu de loisirs",
)
async def delete_managed_establishment(
    establishment_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await _get_managed_establishment(establishment_id, session)
    return await establishment_service.delete_establishment(
        establishment_id,
        session,
        actor,
        request,
    )
