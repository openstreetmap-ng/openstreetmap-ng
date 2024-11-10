from base64 import urlsafe_b64decode
from typing import Required, TypedDict

import orjson


class OpenIDToken(TypedDict, total=False):
    aud: Required[str]
    exp: Required[int]
    iat: Required[int]
    iss: Required[str]
    sub: Required[str]
    name: str
    email: str
    picture: str
    locale: str


def parse_openid_token_no_verify(token: str) -> OpenIDToken:
    payload = token.split('.', maxsplit=2)[1]
    return orjson.loads(urlsafe_b64decode(payload + '=='))
