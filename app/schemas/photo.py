from uuid import UUID

from pydantic import BaseModel


class PhotoPublic(BaseModel):
    id: UUID
    url: str
    thumbnail_url: str | None
    width: int | None
    height: int | None
    alt_text: str | None
    is_cover: bool
    display_order: int