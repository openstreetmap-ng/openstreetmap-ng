from enum import Enum


class OAuth2CodeChallengeMethod(str, Enum):
    plain = 'plain'
    S256 = 'S256'
