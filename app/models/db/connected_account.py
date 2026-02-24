from datetime import datetime
from typing import Literal, TypedDict, get_args

from app.config import (
    FACEBOOK_OAUTH_PUBLIC,
    GITHUB_OAUTH_PUBLIC,
    GOOGLE_OAUTH_PUBLIC,
    MICROSOFT_OAUTH_PUBLIC,
    WIKIMEDIA_OAUTH_PUBLIC,
)
from app.models.proto.settings_connections_types import Provider
from app.models.types import UserId

# TODO: openid
# TODO: migration wikimedia, old value: wikipedia

AUTH_PROVIDERS = frozenset[Provider](get_args(Provider.__value__))

_provider_mapping: dict[Provider, str] = {
    'google': GOOGLE_OAUTH_PUBLIC,
    'facebook': FACEBOOK_OAUTH_PUBLIC,
    'microsoft': MICROSOFT_OAUTH_PUBLIC,
    'github': GITHUB_OAUTH_PUBLIC,
    'wikimedia': WIKIMEDIA_OAUTH_PUBLIC,
}

CONFIGURED_AUTH_PROVIDERS = tuple[Provider, ...](
    provider
    for provider in get_args(Provider.__value__)  #
    if _provider_mapping.get(provider)
)

del _provider_mapping

type AuthProviderAction = Literal['login', 'signup', 'settings']


class ConnectedAccountInit(TypedDict):
    provider: Provider
    uid: str
    user_id: UserId


class ConnectedAccount(ConnectedAccountInit):
    created_at: datetime
