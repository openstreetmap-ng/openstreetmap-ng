from typing import TypedDict

from app.models.db.oauth2_application import ApplicationId
from app.models.db.user import UserId


class UserPref(TypedDict):
    user_id: UserId
    app_id: ApplicationId | None
    key: str
    value: str  # TODO: validate size
