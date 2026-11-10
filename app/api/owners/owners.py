from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cores.db import get_session
from app.dependencies.dependencies import require_owner_account
from app.models import User
from app.schemas.owners import OwnerApplicationPublic
from app.services.owners import owner_application_service


owner_application_router = APIRouter(
    prefix="/owners/applications",
    tags=["Dossier propriétaire"],
)


@owner_application_router.post(
    "",
    response_model=OwnerApplicationPublic,
    status_code=status.HTTP_201_CREATED,
)
async def submit_owner_application(
    registry_document: Annotated[UploadFile, File()],
    partnership_document: Annotated[UploadFile, File()],
    owner: User = Depends(require_owner_account),
    session: AsyncSession = Depends(get_session),
):
    return await owner_application_service.submit(
        owner=owner,
        registry_document=registry_document,
        partnership_document=partnership_document,
        session=session,
    )


@owner_application_router.get(
    "/me",
    response_model=OwnerApplicationPublic,
)
async def get_my_owner_application(
    owner: User = Depends(require_owner_account),
    session: AsyncSession = Depends(get_session),
):
    return await owner_application_service.get_latest(owner.id, session)
