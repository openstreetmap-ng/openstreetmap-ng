from collections.abc import Iterable
from typing import TYPE_CHECKING, NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.auth_mixin import AuthExceptionsMixin

if TYPE_CHECKING:
    from app.models.db.oauth2_token import OAuth2CodeChallengeMethod


class AuthExceptions06Mixin(AuthExceptionsMixin):
    @override
    def unauthorized(self, *, request_basic_auth: bool = False) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail="Couldn't authenticate you",
            headers={'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap API"'} if request_basic_auth else None,
        )

    @override
    def insufficient_scopes(self, scopes: Iterable[str]) -> NoReturn:
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'The request requires higher privileges than authorized ({", ".join(scopes)})',
        )

    @override
    def bad_basic_auth_format(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Malformed basic auth credentials')

    @override
    def oauth2_bearer_missing(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth2 bearer authorization header missing')

    @override
    def oauth2_challenge_method_not_set(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail='OAuth2 verifier provided but code challenge method is not set'
        )

    @override
    def oauth2_bad_verifier(self, code_challenge_method: 'OAuth2CodeChallengeMethod') -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth2 verifier invalid for {code_challenge_method.value} code challenge method',
        )

    @override
    def oauth_bad_client_secret(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth application token invalid')

    @override
    def oauth_bad_user_token(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth user token invalid')

    @override
    def oauth_bad_redirect_uri(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth redirect uri invalid')

    @override
    def oauth_bad_scopes(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth scopes invalid')
