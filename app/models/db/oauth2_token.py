from datetime import datetime
from typing import Literal, NewType, TypedDict, override

from app.models.db.oauth2_application import ApplicationId
from app.models.db.user import UserId
from app.models.scope import PublicScope
from app.models.types import Uri

OAuth2TokenId = NewType('OAuth2TokenId', int)

OAuth2ResponseType = Literal['code']
OAuth2ResponseMode = Literal['query', 'fragment', 'form_post']
OAuth2GrantType = Literal['authorization_code']
OAuth2CodeChallengeMethod = Literal['plain', 'S256']
OAuth2TokenEndpointAuthMethod = Literal['client_secret_post', 'client_secret_basic']


class OAuth2TokenInit(TypedDict):
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
    id: OAuth2TokenId
    created_at: datetime
    authorized_at: datetime | None


def oauth2_token_is_oob(token: OAuth2Token) -> bool:
    """Check if the token is an out-of-band token."""
    return token['redirect_uri'] in {'urn:ietf:wg:oauth:2.0:oob', 'urn:ietf:wg:oauth:2.0:oob:auto'}


class OAuth2TokenOOB:
    __slots__ = ('authorization_code', 'state')

    def __init__(self, authorization_code: str, state: str | None) -> None:
        self.authorization_code = authorization_code
        self.state = state

    @override
    def __str__(self) -> str:
        return self.authorization_code if (self.state is None) else f'{self.authorization_code}#{self.state}'
