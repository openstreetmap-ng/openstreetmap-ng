from datetime import datetime
from typing import NotRequired, TypedDict
from uuid import UUID

from app.models.types import UserId


class AAGUIDInfo(TypedDict):
    name: str
    icon_light: NotRequired[str]  # data:image/png;base64,...
    icon_dark: NotRequired[str]


class UserPasskey(TypedDict):
    credential_id: bytes
    user_id: UserId
    aaguid: UUID
    name: str | None
    algorithm: int
    public_key: bytes
    sign_count: int
    transports: list[str]
    created_at: datetime
    last_used_at: datetime

    # runtime
    aaguid_info: NotRequired[AAGUIDInfo | None]
