from ipaddress import IPv4Address, IPv6Address

import pytest

from app.lib.ip import anonymize_ip, mask_ip


def test_anonymize_ip_ipv4_returns_different_ipv4():
    original = IPv4Address('8.8.8.8')
    anonymized = anonymize_ip(original)

    assert isinstance(anonymized, IPv4Address)
    assert anonymized != original


def test_anonymize_ip_ipv6_returns_different_ipv6():
    original = IPv6Address('2001:1234:5678:9abc:def0:1234:5678:9abc')
    anonymized = anonymize_ip(original)

    assert isinstance(anonymized, IPv6Address)
    assert anonymized != original


def test_anonymize_ip_deterministic():
    ip = IPv4Address('1.1.1.1')
    result1 = anonymize_ip(ip)
    result2 = anonymize_ip(ip)

    assert ip != result1
    assert result1 == result2


def test_anonymize_ip_preserves_local_addresses():
    local_ipv4 = IPv4Address('192.168.1.1')
    local_ipv6 = IPv6Address('::1')

    assert anonymize_ip(local_ipv4) == local_ipv4
    assert anonymize_ip(local_ipv6) == local_ipv6


@pytest.mark.parametrize(
    ('ip', 'expected'),
    [
        (IPv4Address('8.8.8.8'), b'\x08\x08'),
        (IPv4Address('127.0.0.1'), b'\x7f\x00\x00\x01'),
        (
            IPv6Address('2001:1234:5678:9abc:def0:1234:5678:9abc'),
            bytes.fromhex('200112345678'),
        ),
        (IPv6Address('::1'), IPv6Address('::1').packed),
        (IPv6Address('::ffff:8.8.8.8'), b'\xff\x08\x08'),
    ],
)
def test_mask_ip(ip, expected):
    assert mask_ip(ip) == expected
