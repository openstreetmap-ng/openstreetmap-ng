from collections.abc import Sequence
from typing import NotRequired, TypedDict


class OpenIDDiscovery(TypedDict):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    introspection_endpoint: NotRequired[str]
    userinfo_endpoint: str
    revocation_endpoint: str
    jwks_uri: str
    scopes_supported: Sequence[str]
    response_types_supported: Sequence[str]
    response_modes_supported: Sequence[str]
    grant_types_supported: Sequence[str]
    code_challenge_methods_supported: Sequence[str]
    token_endpoint_auth_methods_supported: Sequence[str]
    subject_types_supported: Sequence[str]
    id_token_signing_alg_values_supported: Sequence[str]
    claim_types_supported: Sequence[str]
    claims_supported: Sequence[str]


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
