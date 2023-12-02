from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param

from lib.exceptions import raise_for
from models.db.oauth2_token import OAuth2Token
from repositories.oauth2_token_repository import OAuth2TokenRepository


class OAuth2:
    @staticmethod
    async def parse_and_validate(request: Request) -> OAuth2Token:
        """
        Parse and validate an OAuth2 request.

        Raises exception if the request is not OAuth2 valid.
        """

        authorization = request.headers.get('authorization')

        if not authorization:
            raise_for().oauth2_bearer_missing()

        scheme, param = get_authorization_scheme_param(authorization)

        if scheme.lower() != 'bearer':
            raise_for().oauth2_bearer_missing()

        token = await OAuth2TokenRepository.find_one_authorized_by_token(param)

        if token is None:
            raise_for().oauth_bad_user_token()

        return token
