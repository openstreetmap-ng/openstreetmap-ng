from datetime import datetime
from typing import TypedDict

from app.models.auth_provider import AuthProvider
from app.models.db.user import UserId


class ConnectedAccountInit(TypedDict):
    provider: AuthProvider
    uid: str
    user_id: UserId


class ConnectedAccount(ConnectedAccountInit):
    created_at: datetime
