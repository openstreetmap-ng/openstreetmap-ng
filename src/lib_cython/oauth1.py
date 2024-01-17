import cython
from authlib.oauth1.rfc5849.signature import generate_signature_base_string, hmac_sha1_signature
from authlib.oauth1.rfc5849.wrapper import OAuth1Request
from fastapi import Request

from src.lib.exceptions import raise_for
from src.models.db.oauth1_token import OAuth1Token
from src.repositories.oauth1_token_repository import OAuth1TokenRepository

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')


@cython.cfunc
def _compute_hmac_sha1(request: OAuth1Request, consumer_secret: str, token_secret: str) -> str:
    """
    Compute the HMAC-SHA1 signature for an OAuth1 request.
    """

    base_string = generate_signature_base_string(request)
    signature = hmac_sha1_signature(base_string, consumer_secret, token_secret)

    return signature


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
    async def parse_and_validate(request: OAuth1Request) -> OAuth1Token:
        """
        Parse and validate an OAuth1 request.

        Raises exception if the request is not OAuth1 valid.
        """

        if not request.signature_method or request.signature_method.upper() != 'HMAC-SHA1':
            raise_for().oauth1_unsupported_signature_method(request.signature_method)
        if not request.signature:
            raise_for().oauth1_bad_signature()

        token = await OAuth1TokenRepository.find_one_authorized_by_token(request.token)

        if not token:
            raise_for().oauth_bad_user_token()
        if token.application.consumer_key != request.client_id:
            raise_for().oauth_bad_app_token()

        signature = await _compute_hmac_sha1(
            request,
            token.application.consumer_secret,
            token.token_secret,
        )

        if signature != request.signature:
            raise_for().oauth1_bad_signature()

        return token
