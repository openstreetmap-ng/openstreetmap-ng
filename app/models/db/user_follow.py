from datetime import datetime
from typing import TypedDict

from app.models.db.user import UserDisplay
from app.models.types import UserId


class UserFollow(TypedDict):
    follower_id: UserId
    followee_id: UserId
    created_at: datetime


class UserFollowDisplay(UserDisplay):
    created_at: datetime
    is_following: bool  # Whether current user follows this user
