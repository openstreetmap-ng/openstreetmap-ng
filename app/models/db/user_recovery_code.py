from datetime import datetime
from typing import TypedDict

from app.models.types import UserId


class UserRecoveryCode(TypedDict):
    user_id: UserId
    codes_hashed: list[bytes | None]
    created_at: datetime
