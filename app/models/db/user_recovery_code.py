from datetime import datetime
from typing import TypedDict

from app.models.types import UserId


class UserRecoveryCode(TypedDict):
    user_id: UserId
    secret_encrypted: bytes
    base_index: int
    created_at: datetime
