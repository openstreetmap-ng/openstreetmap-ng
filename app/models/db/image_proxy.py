from datetime import datetime
from typing import TypedDict

from app.models.types import ImageProxyId


class ImageProxyInit(TypedDict):
    url: str


class ImageProxy(ImageProxyInit):
    id: ImageProxyId
    thumbnail: bytes | None
    thumbnail_updated_at: datetime | None
    error_at: datetime | None
    created_at: datetime
    updated_at: datetime
