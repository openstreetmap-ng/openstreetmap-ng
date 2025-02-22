from datetime import datetime
from typing import NewType, NotRequired, TypedDict

from app.lib.image import Image
from app.models.db.user import User, UserId
from app.models.scope import Scope
from app.models.types import StorageKey, Uri

ApplicationId = NewType('ApplicationId', int)
ClientId = NewType('ClientId', str)

_CLIENT_ID_AVATAR_URL_MAP: dict[ClientId, str] = {
    ClientId('SystemApp.web'): '/static/img/favicon/256-app.webp',
    ClientId('SystemApp.id'): '/static/img/brand/id-app.webp',
    ClientId('SystemApp.rapid'): '/static/img/brand/rapid.webp',
}

_DEFAULT_AVATAR_URL = Image.get_avatar_url(None, app=True)


class OAuth2ApplicationInit(TypedDict):
    user_id: UserId | None
    name: str
    client_id: ClientId


class OAuth2Application(OAuth2ApplicationInit):
    id: ApplicationId
    avatar_id: StorageKey | None
    client_secret_hashed: bytes | None
    client_secret_preview: str | None
    confidential: bool
    redirect_uris: list[Uri]
    scopes: list[Scope]
    created_at: datetime
    updated_at: datetime

    # runtime
    user: NotRequired[User]


def oauth2_app_avatar_url(app: OAuth2Application) -> str:
    """Get the url for the application's avatar image."""
    avatar_id = app['avatar_id']
    return (
        _CLIENT_ID_AVATAR_URL_MAP.get(app['client_id'], _DEFAULT_AVATAR_URL)
        if avatar_id is None
        else Image.get_avatar_url('custom', avatar_id)
    )


def oauth2_app_is_system(app: OAuth2Application) -> bool:
    """Check if the application is a system app."""
    return app['user_id'] is None
