import json
import logging

from app.limits import (
    OPENID_DISCOVERY_HTTP_TIMEOUT,
)
from app.models.openid import OpenIDDiscovery
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP

_cache_context = CacheContext('OpenID')


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
        return json.loads(cache.value)
