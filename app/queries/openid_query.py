import logging
from collections.abc import Sequence
from typing import NotRequired, TypedDict

import orjson

from app.limits import (
    OPENID_DISCOVERY_HTTP_TIMEOUT,
)
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP

_cache_context = CacheContext('OpenID')


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


class OpenIDQuery:
    @staticmethod
    async def discovery(base_url: str) -> OpenIDDiscovery:
        """
        Perform OpenID Connect discovery.
        """

        async def factory() -> bytes:
            logging.debug('OpenID discovery cache miss for %r', base_url)
            r = await HTTP.get(
                f'{base_url}/.well-known/openid-configuration',
                timeout=OPENID_DISCOVERY_HTTP_TIMEOUT.total_seconds(),
            )
            r.raise_for_status()
            return r.content

        cache = await CacheService.get(
            base_url,
            context=_cache_context,
            factory=factory,
            ttl=OPENID_DISCOVERY_HTTP_TIMEOUT,
        )
        return orjson.loads(cache.value)
