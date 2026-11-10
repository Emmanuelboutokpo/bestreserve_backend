
from __future__ import annotations

import time
from uuid import uuid4

import cloudinary
from cloudinary import uploader
from cloudinary.utils import private_download_url
from starlette.concurrency import run_in_threadpool

from app.config import settings


AVATAR_FOLDER = "bestreserv/avatars"
OWNER_DOCUMENT_FOLDER = "bestreserv/owner-documents"


def configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def extract_public_id_from_url(
    url: str | None,
    expected_folder: str | None = None,
) -> str | None:
    if not url:
        return None

    try:
        parts = url.split("/upload/")
        if len(parts) < 2:
            return None

        path = parts[1]

        # Retirer le préfixe de version Cloudinary, par exemple v123456/
        if path.startswith("v") and "/" in path:
            path = path.split("/", 1)[1]

        # Retirer l'extension
        public_id = path.rsplit(".", 1)[0]

        if expected_folder and not public_id.startswith(
            f"{expected_folder}/"
        ):
            return None

        return public_id

    except Exception:
        return None


async def upload_image(
    contents: bytes,
    *,
    folder: str,
    transformation: dict | None = None,
    allowed_formats: list[str] | None = None,
) -> dict:
    configure_cloudinary()

    options: dict = {
        "folder": folder,
        "resource_type": "image",
    }

    if allowed_formats:
        options["allowed_formats"] = allowed_formats

    if transformation:
        options["transformation"] = transformation

    return await run_in_threadpool(
        uploader.upload,
        contents,
        **options,
    )


async def destroy_image(
    public_id: str | None,
    *,
    expected_folder: str | None = None,
) -> None:
    if not public_id:
        return

    if expected_folder and not public_id.startswith(
        f"{expected_folder}/"
    ):
        raise ValueError(
            f"Identifiant Cloudinary invalide "
            f"(dossier attendu : '{expected_folder}')."
        )

    configure_cloudinary()

    result = await run_in_threadpool(
        uploader.destroy,
        public_id,
        resource_type="image",
    )

    if result.get("result") not in ("ok", "not found"):
        raise RuntimeError(
            f"Échec de suppression Cloudinary : {result}"
        )


async def upload_owner_document(contents: bytes) -> dict:
    configure_cloudinary()
    public_id = uuid4().hex
    return await run_in_threadpool(
        uploader.upload,
        contents,
        folder=OWNER_DOCUMENT_FOLDER,
        public_id=public_id,
        resource_type="raw",
        type="authenticated",
        overwrite=False,
        use_filename=False,
    )


async def destroy_owner_document(public_id: str) -> None:
    configure_cloudinary()
    result = await run_in_threadpool(
        uploader.destroy,
        public_id,
        resource_type="raw",
        type="authenticated",
    )
    if result.get("result") not in ("ok", "not found"):
        raise RuntimeError(
            f"Échec de suppression du document Cloudinary : {result}"
        )


def owner_document_download_url(public_id: str, filename: str) -> str:
    configure_cloudinary()
    extension = filename.rsplit(".", 1)[-1].lower()
    return private_download_url(
        public_id,
        extension,
        resource_type="raw",
        type="authenticated",
        attachment=True,
        expires_at=int(time.time()) + 600,
    )
