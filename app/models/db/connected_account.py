from datetime import datetime
from typing import Literal, TypedDict, get_args

from app.config import (
    FACEBOOK_OAUTH_PUBLIC,
    GITHUB_OAUTH_PUBLIC,
    GOOGLE_OAUTH_PUBLIC,
    MICROSOFT_OAUTH_PUBLIC,
    WIKIMEDIA_OAUTH_PUBLIC,
)
from app.models.types import UserId

AuthProvider = Literal['google', 'facebook', 'microsoft', 'github', 'wikimedia']
# TODO: openid
# TODO: migration wikimedia, old value: wikipedia

AUTH_PROVIDERS = frozenset[AuthProvider](get_args(AuthProvider))

_provider_mapping: dict[AuthProvider, str] = {
    'google': GOOGLE_OAUTH_PUBLIC,
    'facebook': FACEBOOK_OAUTH_PUBLIC,
    'microsoft': MICROSOFT_OAUTH_PUBLIC,
    'github': GITHUB_OAUTH_PUBLIC,
    'wikimedia': WIKIMEDIA_OAUTH_PUBLIC,
}

CONFIGURED_AUTH_PROVIDERS = tuple[AuthProvider, ...](
    provider
    for provider in get_args(AuthProvider)  #
    if _provider_mapping.get(provider)
)

del _provider_mapping

AuthProviderAction = Literal['login', 'signup', 'settings']


class ConnectedAccountInit(TypedDict):
    provider: AuthProvider
    uid: str
    user_id: UserId


class ConnectedAccount(ConnectedAccountInit):
    created_at: datetime
