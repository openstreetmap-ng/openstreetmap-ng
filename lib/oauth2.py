from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param

from lib.exceptions import exceptions
from models.db.oauth2_token import OAuth2Token


class OAuth2:
    @staticmethod
    async def parse_and_validate(request: Request) -> OAuth2Token:
        """
        Parse and validate an OAuth2 request.

        Raises exception if the request is not OAuth2 valid.
        """

        authorization = request.headers.get('authorization')

        if not authorization:
            exceptions().raise_for_oauth2_bearer_missing()

        scheme, param = get_authorization_scheme_param(authorization)

        if scheme.lower() != 'bearer':
            exceptions().raise_for_oauth2_bearer_missing()

        token = await OAuth2Token.find_one_by_key_with_(param)

        if token is None:
            exceptions().raise_for_oauth_bad_user_token()

        return token
