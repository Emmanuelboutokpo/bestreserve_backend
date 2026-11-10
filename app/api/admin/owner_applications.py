from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.models import User
from app.models.enums import OwnerApplicationStatus
from app.schemas.owners import (
    OwnerApplicationDecision,
    OwnerApplicationPublic,
)
from app.services.owners import owner_application_service


admin_owner_application_router = APIRouter(
    prefix="/admin/owner-applications",
    tags=["Administration - Dossiers propriétaires"],
    dependencies=[Depends(require_admin)],
)


@admin_owner_application_router.get(
    "/{application_id}",
    response_model=OwnerApplicationPublic,
)
async def get_owner_application(
    application_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await owner_application_service.get_application(
        application_id,
        session,
    )


@admin_owner_application_router.get(
    "",
    response_model=list[OwnerApplicationPublic],
)
async def list_owner_applications(
    application_status: OwnerApplicationStatus | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await owner_application_service.list_applications(
        session,
        application_status=application_status,
        limit=limit,
        offset=offset,
    )


@admin_owner_application_router.patch(
    "/{application_id}",
    response_model=OwnerApplicationPublic,
)
async def review_owner_application(
    application_id: UUID,
    decision: OwnerApplicationDecision,
    reviewer: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await owner_application_service.review(
        application_id=application_id,
        decision=decision,
        reviewer=reviewer,
        session=session,
    )
