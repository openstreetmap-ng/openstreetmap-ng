from abc import ABC

from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param

from lib.exceptions import Exceptions
from models.collections.oauth2_token import OAuth2Token


class OAuth2(ABC):
    @staticmethod
    async def parse_and_validate(request: Request) -> OAuth2Token:
        authorization = request.headers.get('authorization')

        if not authorization:
            Exceptions.get().raise_for_oauth2_bearer_missing()

        scheme, param = get_authorization_scheme_param(authorization)

        if scheme.lower() != 'bearer':
            Exceptions.get().raise_for_oauth2_bearer_missing()

        token = await OAuth2Token.find_one_by_key_with_(param)

        if token is None:
            Exceptions.get().raise_for_oauth_bad_user_token()

        return token
