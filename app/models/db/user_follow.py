from datetime import datetime
from typing import TypedDict

from app.models.types import UserId


class UserFollow(TypedDict):
    follower_id: UserId
    followee_id: UserId
    created_at: datetime
