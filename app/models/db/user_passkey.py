from datetime import datetime
from typing import TypedDict

from app.models.types import UserId


class UserPasskey(TypedDict):
    credential_id: bytes
    user_id: UserId
    name: str
    algorithm: int
    public_key: bytes
    sign_count: int
    transports: list[str]
    created_at: datetime
    last_used_at: datetime
