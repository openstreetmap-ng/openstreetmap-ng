from datetime import datetime
from typing import Literal, NotRequired, TypedDict, override

from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import User
from app.models.scope import PublicScope
from app.models.types import ApplicationId, OAuth2TokenId, Uri, UserId

OAuth2ResponseType = Literal['code']
OAuth2ResponseMode = Literal['query', 'fragment', 'form_post']
OAuth2GrantType = Literal['authorization_code']
OAuth2CodeChallengeMethod = Literal['plain', 'S256']
OAuth2TokenEndpointAuthMethod = Literal['client_secret_post', 'client_secret_basic']


class OAuth2TokenInit(TypedDict):
    id: OAuth2TokenId
    user_id: UserId
    application_id: ApplicationId
    name: str | None  # PATs only
    token_hashed: bytes | None
    token_preview: str | None  # PATs only
    redirect_uri: Uri | None
    scopes: list[PublicScope]
    code_challenge_method: OAuth2CodeChallengeMethod | None
    code_challenge: str | None  # TODO: validate size


class OAuth2Token(OAuth2TokenInit):
    created_at: datetime
    authorized_at: datetime | None

    # runtime
    user: NotRequired[User]
    application: NotRequired[OAuth2Application]


def oauth2_token_is_oob(
    token_or_uri: OAuth2Token | OAuth2TokenInit | Uri | None, /
) -> bool:
    """Check if the token is an out-of-band token."""
    return (
        token_or_uri['redirect_uri']  #
        if isinstance(token_or_uri, dict)
        else token_or_uri
    ) in {
        'urn:ietf:wg:oauth:2.0:oob',
        'urn:ietf:wg:oauth:2.0:oob:auto',
    }


class OAuth2TokenOOB:
    __slots__ = ('authorization_code', 'state')

    def __init__(self, authorization_code: str, state: str | None) -> None:
        self.authorization_code = authorization_code
        self.state = state

    @override
    def __str__(self) -> str:
        return (
            self.authorization_code
            if self.state is None
            else f'{self.authorization_code}#{self.state}'
        )
