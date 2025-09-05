from functools import lru_cache
from ipaddress import IPv4Address, IPv6Address

from app.lib.crypto import hmac_bytes
from app.lib.testmethod import testmethod


@testmethod
@lru_cache(maxsize=512)
def anonymize_ip[T: IPv4Address | IPv6Address](ip: T) -> T:
    """
    Deterministically anonymize an IP address using the instance secret.

    The same IP will always produce the same anonymized result.
    IPv4 addresses are mapped to IPv4, IPv6 addresses are mapped to IPv6.
    """
    if not ip.is_global:
        return ip

    hash_digest = hmac_bytes(ip.packed)
    return (  # type: ignore
        IPv4Address(hash_digest[:4])
        if isinstance(ip, IPv4Address)
        else IPv6Address(hash_digest[:16])
    )
