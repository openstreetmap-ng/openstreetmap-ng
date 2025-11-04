from datetime import datetime
from typing import TypedDict

from app.models.types import ImageProxyId


class ImageProxy(TypedDict):
    id: ImageProxyId
    url: str
    width: int | None
    height: int | None
    thumbnail: str | None
    thumbnail_updated_at: datetime | None
