from datetime import datetime
from typing import TypedDict

from app.models.types import UserId


class UserTOTP(TypedDict):
    """User TOTP credential."""

    user_id: UserId
    secret_encrypted: bytes
    created_at: datetime
    last_used_at: datetime | None
