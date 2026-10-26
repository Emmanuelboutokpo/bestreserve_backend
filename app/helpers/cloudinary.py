
from __future__ import annotations

import cloudinary
from cloudinary import uploader
from starlette.concurrency import run_in_threadpool

from app.config import settings


AVATAR_FOLDER = "bestreserv/avatars"


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
