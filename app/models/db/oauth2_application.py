from datetime import datetime
from typing import NewType, NotRequired, TypedDict

from app.lib.image import DEFAULT_APP_AVATAR_URL, Image
from app.models.db.user import UserDisplay
from app.models.scope import PublicScope
from app.models.types import ApplicationId, ClientId, StorageKey, UserId

OAuth2Uri = NewType('OAuth2Uri', str)

SYSTEM_APP_WEB_CLIENT_ID = ClientId('SystemApp.web')
SYSTEM_APP_PAT_CLIENT_ID = ClientId('SystemApp.pat')
SYSTEM_APP_ID_CLIENT_ID = ClientId('SystemApp.id')
SYSTEM_APP_RAPID_CLIENT_ID = ClientId('SystemApp.rapid')

_CLIENT_ID_AVATAR_URL_MAP: dict[ClientId, str] = {
    SYSTEM_APP_WEB_CLIENT_ID: '/static/img/favicon/256-app.webp',
    SYSTEM_APP_ID_CLIENT_ID: '/static/img/brand/id-app.webp',
    SYSTEM_APP_RAPID_CLIENT_ID: '/static/img/brand/rapid.webp',
}


class OAuth2ApplicationInit(TypedDict):
    id: ApplicationId
    user_id: UserId | None
    name: str
    client_id: ClientId


class OAuth2Application(OAuth2ApplicationInit):
    avatar_id: StorageKey | None
    client_secret_hashed: bytes | None
    client_secret_preview: str | None
    confidential: bool
    redirect_uris: list[OAuth2Uri]
    scopes: list[PublicScope]
    created_at: datetime
    updated_at: datetime

    # runtime
    user: NotRequired[UserDisplay]


def oauth2_app_avatar_url(app: OAuth2Application) -> str:
    """Get the url for the application's avatar image."""
    avatar_id = app['avatar_id']
    return (
        _CLIENT_ID_AVATAR_URL_MAP.get(app['client_id'], DEFAULT_APP_AVATAR_URL)
        if avatar_id is None
        else Image.get_avatar_url('custom', avatar_id)
    )


def oauth2_app_is_system(app: OAuth2Application) -> bool:
    """Check if the application is a system app."""
    return app['user_id'] is None
