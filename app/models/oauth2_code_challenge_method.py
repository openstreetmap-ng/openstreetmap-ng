from base64 import urlsafe_b64encode
from hashlib import sha256

from app.models.base_enum import BaseEnum


class OAuth2CodeChallengeMethod(BaseEnum):
    plain = 'plain'
    S256 = 'S256'

    @staticmethod
    def compute_s256(verifier: str) -> str:
        """
        Compute the S256 code challenge from the verifier.
        """

        verifier_bytes = verifier.encode()
        verifier_hashed = sha256(verifier_bytes).digest()
        verifier_base64 = urlsafe_b64encode(verifier_hashed).decode().rstrip('=')

        return verifier_base64
