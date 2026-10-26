
from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
    Request
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.cores.db import get_session
from app.dependencies.dependencies import require_admin
from app.helpers.cloudinary import (
    upload_image,
    destroy_image,
    extract_public_id_from_url,
)
from app.models import Establishment, Photo, User
from app.services.establishment import EstablishmentService


establishment_media_router = APIRouter(
    prefix="/admin",
    tags=["Admin - Establishment Media"],
    dependencies=[Depends(require_admin)],
)

establishment_service = EstablishmentService()

ESTABLISHMENT_MEDIA_FOLDER = "bestreserv/establishments"
MAX_IMAGE_SIZE = 5 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

async def _get_establishment(
    db: AsyncSession,
    establishment_id: UUID,
) -> Establishment:
    establishment = await db.get(Establishment, establishment_id)

    if establishment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Établissement introuvable.",
        )

    return establishment


async def _get_photo(
    db: AsyncSession,
    photo_id: UUID,
) -> Photo:
    photo = await db.get(Photo, photo_id)

    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo introuvable.",
        )

    return photo



@establishment_media_router.post(
    "/establishments/{establishment_id}/photos",
    status_code=status.HTTP_201_CREATED,
)
async def add_establishment_photos(
    establishment_id: UUID,
    request: Request,
    files: list[UploadFile] = File(
        ...,
        description="Sélectionnez une ou plusieurs photos",
    ),
    db: AsyncSession = Depends(get_session),
    actor: User = Depends(require_admin),
):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Veuillez sélectionner au moins une photo.",
        )

    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Vous pouvez ajouter au maximum 10 photos à la fois.",
        )

    result = await db.execute(
        select(Establishment).where(
            Establishment.id == establishment_id
        )
    )
    establishment = result.scalar_one_or_none()

    if establishment is None:
        raise HTTPException(
            status_code=404,
            detail="Établissement introuvable.",
        )

    uploaded_images = []

    try:
        for file in files:
            if file.content_type not in ALLOWED_CONTENT_TYPES :
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{file.filename} : format non autorisé. "
                        "Formats acceptés : JPEG, PNG et WebP."
                    ),
                )

            content = await file.read()

            if not content:
                raise HTTPException(
                    status_code=400,
                    detail=f"Le fichier {file.filename} est vide.",
                )

            if len(content) > 5 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"{file.filename} dépasse la limite de 5 Mo.",
                )

            # Upload Cloudinary : la fonction est asynchrone
            uploaded = await upload_image(
                content,
                folder="bestreserv/establishments",
                allowed_formats=["jpg", "jpeg", "png", "webp"],
            )

            uploaded_images.append(uploaded)

            photo = Photo(
                establishment_id=establishment.id,
                url=uploaded["secure_url"],
                public_id=uploaded["public_id"],
            )

            db.add(photo)
            await db.flush()

            # _audit est synchrone : ne pas utiliser await
            establishment_service._audit(
                db=db,
                actor=actor,
                action="ESTABLISHMENT_PHOTO_CREATED",
                establishment=establishment,
                request=request,
                metadata={
                    "photo_id": str(photo.id),
                    "public_id": uploaded["public_id"],
                    "filename": file.filename,
                },
            )

        await db.commit()

        return {
            "message": (
                f"{len(uploaded_images)} photo(s) "
                "ajoutée(s) avec succès."
            ),
            "count": len(uploaded_images),
        }

    except Exception:
        await db.rollback()

        # Nettoyage des images Cloudinary si la transaction échoue
        for uploaded in uploaded_images:
            try:
                await destroy_image(
                    uploaded["public_id"],
                    expected_folder="bestreserv/establishments",
                )
            except Exception:
                # Préserver l'erreur initiale
                pass

        raise

    finally:
        for file in files:
            await file.close()


@establishment_media_router.delete("/photos/{photo_id}")
async def delete_establishment_photo(
    photo_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session),
    actor: User = Depends(require_admin),
):
    """Supprime une photo et journalise l'opération."""

    photo = await _get_photo(db, photo_id)

    establishment = await _get_establishment(
        db,
        photo.establishment_id,
    )

    public_id = extract_public_id_from_url(
        photo.url,
        expected_folder=ESTABLISHMENT_MEDIA_FOLDER,
    )

    was_cover = photo.is_cover
    photo_id_str = str(photo.id)

    try:
        await db.delete(photo)

        if was_cover:
            result = await db.execute(
                select(Photo)
                .where(
                    Photo.establishment_id == establishment.id,
                    Photo.id != photo.id,
                )
                .order_by(Photo.id)
                .limit(1)
            )
            replacement = result.scalar_one_or_none()

            if replacement:
                replacement.is_cover = True

        # Correction : transmettre establishment, pas establishment_id.
        await establishment_service._audit(
            db=db,
            actor=actor,
            action="ESTABLISHMENT_PHOTO_DELETED",
            establishment=establishment,
            request=request,
            metadata={"photo_id": photo_id_str},
        )

        await db.commit()

    except Exception:
        await db.rollback()
        raise

    # Supprimer l'image distante après la validation SQL.
    # Si Cloudinary échoue, la suppression SQL reste effective.
    if public_id:
        try:
            await destroy_image(
                public_id,
                expected_folder=ESTABLISHMENT_MEDIA_FOLDER,
            )
        except Exception:
            # Prévoir un mécanisme de reprise pour les images orphelines.
            pass

    return {"message": "Photo supprimée avec succès."}


@establishment_media_router.patch("/photos/{photo_id}/cover")
async def set_establishment_cover(
    photo_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_session),
    actor: User = Depends(require_admin),
):
    """Définit une photo comme couverture de l'établissement."""

    photo = await _get_photo(db, photo_id)

    establishment = await _get_establishment(
        db,
        photo.establishment_id,
    )

    try:
        result = await db.execute(
            select(Photo).where(
                Photo.establishment_id == establishment.id,
            )
        )
        photos = result.scalars().all()

        for item in photos:
            item.is_cover = item.id == photo.id

        # Correction : transmettre establishment, pas establishment_id.
        await establishment_service._audit(
            db=db,
            actor=actor,
            action="ESTABLISHMENT_COVER_UPDATED",
            establishment=establishment,
            request=request,
            metadata={"photo_id": str(photo.id)},
        )

        await db.commit()

    except Exception:
        await db.rollback()
        raise

    return {
        "message": "Photo de couverture mise à jour.",
        "photo_id": str(photo.id),
    }
