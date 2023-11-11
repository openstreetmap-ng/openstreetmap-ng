from abc import ABC

from authlib.oauth1.rfc5849.signature import (generate_signature_base_string,
                                              hmac_sha1_signature)
from authlib.oauth1.rfc5849.wrapper import OAuth1Request
from fastapi import Request

from lib.exceptions import Exceptions
from models.db.oauth1_token import OAuth1Token


class OAuth1(ABC):
    @staticmethod
    async def convert_request(request: Request) -> OAuth1Request:
        '''
        Convert a FastAPI request to an OAuth1Request.
        '''

        return OAuth1Request(
            method=request.method,
            uri=str(request.url),
            body=await request.form(),
            headers=request.headers)

    @staticmethod
    async def compute_hmac_sha1(request: OAuth1Request, app_secret: str, token_secret: str) -> str:
        base_string = generate_signature_base_string(request)
        signature = hmac_sha1_signature(base_string, app_secret, token_secret)
        return signature

    @staticmethod
    async def parse_and_validate(request: OAuth1Request) -> OAuth1Token:
        if not request.signature_method or request.signature_method.upper() != 'HMAC-SHA1':
            Exceptions.get().raise_for_oauth1_unsupported_signature_method(request.signature_method)
        if not request.signature:
            Exceptions.get().raise_for_oauth1_bad_signature()

        token = await OAuth1Token.find_one_by_key_with_(request.token)

        if not token:
            Exceptions.get().raise_for_oauth_bad_user_token()
        if token.app_.key_public != request.client_id:
            Exceptions.get().raise_for_oauth_bad_app_token()

        signature = await OAuth1.compute_hmac_sha1(request, token.app_.key_secret, token.key_secret)

        if signature != request.signature:
            Exceptions.get().raise_for_oauth1_bad_signature()

        return token
