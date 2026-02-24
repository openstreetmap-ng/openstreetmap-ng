from functools import lru_cache
from ipaddress import IPv4Address, IPv6Address
from typing import TypeVar

from app.lib.crypto import hmac_bytes
from app.lib.testmethod import testmethod

_T = TypeVar('_T', bound=IPv4Address | IPv6Address)


@testmethod
@lru_cache(maxsize=512)
def anonymize_ip(ip: _T) -> _T:
    """
    Deterministically anonymize an IP address using the instance secret.

    The same IP always produces the same anonymized result.
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


def mask_ip(ip: IPv4Address | IPv6Address):
    """
    Return packed bytes for IP display transport.

    Encoded lengths:
    - 2 bytes: masked IPv4 (/16 visible)
    - 3 bytes: masked IPv4-mapped IPv6 (`0xff` marker + /16 visible)
    - 4 bytes: full IPv4 (non-global)
    - 6 bytes: masked IPv6 (/48 visible)
    - 16 bytes: full IPv6 (non-global)
    """
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped:
        mapped = ip.ipv4_mapped
        if not mapped.is_global:
            return ip.packed
        octets = mapped.packed
        return bytes((0xFF, octets[0], octets[1]))

    if not ip.is_global:
        return ip.packed

    if isinstance(ip, IPv4Address):
        return ip.packed[:2]

    return ip.packed[:6]
