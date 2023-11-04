from models.base_enum import BaseEnum


class OAuth2CodeChallengeMethod(BaseEnum):
    plain = 'plain'
    S256 = 'S256'
