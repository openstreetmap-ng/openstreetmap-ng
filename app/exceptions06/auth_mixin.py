from collections.abc import Sequence
from typing import NoReturn, override

from fastapi import status

from app.exceptions.api_error import APIError
from app.exceptions.auth_mixin import AuthExceptionsMixin
from app.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod


class AuthExceptions06Mixin(AuthExceptionsMixin):
    @override
    def unauthorized(self, *, request_basic_auth: bool = False) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail="Couldn't authenticate you",
            headers={'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap API"'} if request_basic_auth else None,
        )

    @override
    def insufficient_scopes(self, scopes: Sequence[str]) -> NoReturn:
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'The request requires higher privileges than authorized ({", ".join(scopes)})',
        )

    @override
    def bad_basic_auth_format(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Malformed basic auth credentials')

    @override
    def oauth1_timestamp_out_of_range(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth timestamp out of range')

    @override
    def oauth1_nonce_missing(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth nonce missing')

    @override
    def oauth1_bad_nonce(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth nonce invalid')

    @override
    def oauth1_nonce_used(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth nonce already used')

    @override
    def oauth1_bad_verifier(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth verifier invalid')

    @override
    def oauth1_unsupported_signature_method(self, method: str) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail=f'OAuth unsupported signature method {method!r}')

    @override
    def oauth1_bad_signature(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth signature invalid')

    @override
    def oauth2_bearer_missing(self) -> NoReturn:
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth2 bearer authorization header missing')

    @override
    def oauth2_challenge_method_not_set(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail='OAuth2 verifier provided but code challenge method is not set'
        )

    @override
    def oauth2_bad_verifier(self, code_challenge_method: OAuth2CodeChallengeMethod) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth2 verifier invalid for {code_challenge_method.value} code challenge method',
        )

    @override
    def oauth_bad_app_token(self) -> NoReturn:
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
