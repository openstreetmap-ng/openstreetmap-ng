from authlib.oauth1.rfc5849.signature import generate_signature_base_string, hmac_sha1_signature
from authlib.oauth1.rfc5849.wrapper import OAuth1Request
from fastapi import Request

from lib.exceptions import raise_for
from models.db.oauth1_token import OAuth1Token


class OAuth1:
    @staticmethod
    async def convert_request(request: Request) -> OAuth1Request:
        """
        Convert a FastAPI request to an OAuth1Request.
        """

        return OAuth1Request(
            method=request.method,
            uri=str(request.url),
            body=await request.form(),
            headers=request.headers,
        )

    @staticmethod
    async def compute_hmac_sha1(request: OAuth1Request, app_secret: str, token_secret: str) -> str:
        """
        Compute the HMAC-SHA1 signature for an OAuth1 request.
        """

        base_string = generate_signature_base_string(request)
        signature = hmac_sha1_signature(base_string, app_secret, token_secret)
        return signature

    @staticmethod
    async def parse_and_validate(request: OAuth1Request) -> OAuth1Token:
        """
        Parse and validate an OAuth1 request.

        Raises exception if the request is not OAuth1 valid.
        """

        if not request.signature_method or request.signature_method.upper() != 'HMAC-SHA1':
            raise_for().oauth1_unsupported_signature_method(request.signature_method)
        if not request.signature:
            raise_for().oauth1_bad_signature()

        token = await OAuth1Token.find_one_by_key_with_(request.token)

        if not token:
            raise_for().oauth_bad_user_token()
        if token.app_.key_public != request.client_id:
            raise_for().oauth_bad_app_token()

        signature = await OAuth1.compute_hmac_sha1(request, token.app_.key_secret, token.key_secret)

        if signature != request.signature:
            raise_for().oauth1_bad_signature()

        return token
