from app.lib.exceptions_context import raise_for
from app.models.db.oauth2_token import OAuth2Token
from app.repositories.oauth2_token_repository import OAuth2TokenRepository


class OAuth2:
    @staticmethod
    async def parse_and_validate(scheme: str, param: str) -> OAuth2Token:
        """
        Parse and validate an OAuth2 request.

        Raises exception if the request is not OAuth2 valid.
        """

        if scheme != 'Bearer':
            raise_for().oauth2_bearer_missing()

        token = await OAuth2TokenRepository.find_one_authorized_by_token(param)
        if token is None:
            raise_for().oauth_bad_user_token()

        return token
