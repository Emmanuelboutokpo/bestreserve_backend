from pydantic import BaseModel
import uuid
from typing import List, Optional
from datetime import datetime

class StyleImageRead(BaseModel):
    url: str
    mediaType: str

class TailorPublicRead(BaseModel):
    id: uuid.UUID
    firstName: str
    lastName: str
    img: Optional[str] = None

class StyleReadWithDetails(BaseModel):
    id: uuid.UUID
    model: str
    description: Optional[str]
    categoryName: Optional[str] = None  
    created_at: datetime
    images: List[StyleImageRead]
    tailor: Optional[TailorPublicRead] = None 


class StylePaginationResponse(BaseModel):
    items: List[StyleReadWithDetails]
    total: int
    page_info: dict # Contient has_more et count