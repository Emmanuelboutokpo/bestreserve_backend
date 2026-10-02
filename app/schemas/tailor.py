from pydantic import BaseModel, Field
from typing import Optional, Annotated
from uuid import UUID

class TailorPublicResponse(BaseModel):
    id: UUID
    firstName : Annotated[str, Field(..., description="Le first name du user", min_length=1, max_length=50)]
    lastName : Annotated[str, Field(..., description="Le last name du user", min_length=1, max_length=50)]
    bio  : Optional[str] = None
    img: Optional[str] = None
    ratingAvg: float
    totalReviews: int

    class Config:
        from_attributes = True


class TailorPrivate(TailorPublicResponse):
    telephone: str
    address: str

 