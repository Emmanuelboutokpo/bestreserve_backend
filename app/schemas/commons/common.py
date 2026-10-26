from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel
import re

T = TypeVar("T")


class MessageResponse(BaseModel):
    """Réponse simple avec un message."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Réponse d'erreur standardisée."""
    success: bool = False
    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Réponse paginée générique."""
    success: bool = True
    data: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginationParams(BaseModel):
    """Paramètres de pagination."""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def slug(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip().lower()

    if not value:
        raise ValueError("Le slug ne peut pas être vide.")

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError(
            "Le slug doit contenir uniquement des lettres minuscules, "
            "des chiffres et des tirets."
        )

    return value