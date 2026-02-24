from abc import abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, NoReturn

from starlette import status

from app.exceptions.api_error import APIError

if TYPE_CHECKING:
    from app.models.db.oauth2_token import OAuth2CodeChallengeMethod


class AuthExceptionsMixin:
    def unauthorized(self, *, request_basic_auth: bool = False):
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='Unauthorized',
            headers=(
                {'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap"'}
                if request_basic_auth
                else None
            ),
        )

    def insufficient_scopes(self, scopes: Iterable[str]) -> NoReturn:
        required_scopes = ' '.join(sorted(set(scopes)))
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'insufficient_scope: scope="{required_scopes}"',
        )

    def bad_user_token_struct(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_token')

    @abstractmethod
    def bad_basic_auth_format(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth2_bearer_missing(self) -> NoReturn:
        raise NotImplementedError

    def oauth2_bad_code_challenge_params(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_code_challenge')

    def oauth2_challenge_method_not_set(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail='invalid_code_challenge_method'
        )

    @abstractmethod
    def oauth2_bad_verifier(
        self, code_challenge_method: 'OAuth2CodeChallengeMethod'
    ) -> NoReturn:
        raise NotImplementedError

    def oauth_bad_client_id(self):
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='invalid_client')

    def oauth_bad_client_secret(self):
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='invalid_client')

    def oauth_bad_user_token(self):
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='invalid_token')

    def oauth_bad_redirect_uri(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_redirect_uri')

    def oauth_bad_scopes(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_scope')
