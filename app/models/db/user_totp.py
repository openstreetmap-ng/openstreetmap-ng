from datetime import datetime
from typing import TypedDict

from app.models.types import UserId


class UserTOTP(TypedDict):
    user_id: UserId
    secret_encrypted: bytes
    created_at: datetime
