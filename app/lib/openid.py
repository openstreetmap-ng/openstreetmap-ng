import json
from base64 import urlsafe_b64decode
from typing import NotRequired, TypedDict


class OpenIDToken(TypedDict):
    aud: str
    exp: int
    iat: int
    iss: str
    sub: str
    name: NotRequired[str]
    email: NotRequired[str]
    picture: NotRequired[str]
    locale: NotRequired[str]


def parse_openid_token_no_verify(token: str) -> OpenIDToken:
    payload = token.split('.', maxsplit=2)[1]
    return json.loads(urlsafe_b64decode(payload + '=='))
