import cython
from authlib.oauth1.rfc5849.signature import generate_signature_base_string, hmac_sha1_signature
from authlib.oauth1.rfc5849.wrapper import OAuth1Request
from fastapi import Request

from app.lib.exceptions_context import raise_for
from app.models.db.oauth1_token import OAuth1Token
from app.queries.oauth1_token_query import OAuth1TokenQuery


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
        if request.signature_method is None or request.signature_method.upper() != 'HMAC-SHA1':
            raise_for().oauth1_unsupported_signature_method(request.signature_method)
        if request.signature is None:
            raise_for().oauth1_bad_signature()

        token = await OAuth1TokenQuery.find_one_authorized_by_token(request.token)
        if token is None:
            raise_for().oauth_bad_user_token()

        token_application = token.application
        if token_application.consumer_key != request.client_id:
            raise_for().oauth_bad_app_token()

        signature = await _compute_hmac_sha1(
            request,
            token_application.consumer_secret,
            token.token_secret,
        )
        if signature != request.signature:
            raise_for().oauth1_bad_signature()

        return token
