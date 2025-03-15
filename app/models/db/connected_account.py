from datetime import datetime
from typing import Literal, TypedDict, get_args

from app.models.types import UserId

AuthProvider = Literal['google', 'facebook', 'microsoft', 'github', 'wikimedia']
# TODO: openid
# TODO: migration wikimedia, old value: wikipedia

AUTH_PROVIDERS: frozenset[AuthProvider] = frozenset(get_args(AuthProvider))

AuthProviderAction = Literal['login', 'signup', 'settings']


class ConnectedAccountInit(TypedDict):
    provider: AuthProvider
    uid: str
    user_id: UserId


class ConnectedAccount(ConnectedAccountInit):
    created_at: datetime
