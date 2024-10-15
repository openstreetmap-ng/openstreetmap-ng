from abc import abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, NoReturn

from starlette import status

from app.exceptions.api_error import APIError

if TYPE_CHECKING:
    from app.models.db.oauth2_token import OAuth2CodeChallengeMethod


class AuthExceptionsMixin:
    @abstractmethod
    def unauthorized(self, *, request_basic_auth: bool = False) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='Unauthorized',
            headers={'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap"'} if request_basic_auth else None,
        )

    @abstractmethod
    def insufficient_scopes(self, scopes: Iterable[str]) -> NoReturn:
        raise NotImplementedError

    def bad_user_token_struct(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Invalid user token')

    @abstractmethod
    def bad_basic_auth_format(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth2_bearer_missing(self) -> NoReturn:
        raise NotImplementedError

    def oauth2_bad_code_challenge_params(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Invalid code challenge parameters')

    def oauth2_challenge_method_not_set(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail='code_verifier was provided but code_challenge_method is not set'
        )

    @abstractmethod
    def oauth2_bad_verifier(self, code_challenge_method: 'OAuth2CodeChallengeMethod') -> NoReturn:
        raise NotImplementedError

    def oauth_bad_client_id(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='Invalid client ID')

    def oauth_bad_client_secret(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='Invalid client secret')

    @abstractmethod
    def oauth_bad_user_token(self) -> NoReturn:
        raise NotImplementedError

    def oauth_bad_redirect_uri(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Invalid redirect URI')

    @abstractmethod
    def oauth_bad_scopes(self) -> NoReturn:
        raise NotImplementedError
