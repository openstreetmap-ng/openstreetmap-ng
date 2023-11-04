from ipaddress import IPv6Address, IPv6Network

from models.collections.acl import ACL


class ACLIPv4(ACL):
    ipv6_high_min: int
    ipv6_low_min: int
    ipv6_high_max: int
    ipv6_low_max: int

    @staticmethod
    def net_to_int(net: IPv6Network) -> tuple[int, int, int, int]:
        min_ip = int(net.network_address)
        max_ip = int(net.broadcast_address)
        return (min_ip >> 64, min_ip & ((1 << 64) - 1),
                max_ip >> 64, max_ip & ((1 << 64) - 1))

    @staticmethod
    def ip_to_int(ip: IPv6Address) -> tuple[int, int]:
        ip_int = int(ip)
        return ip_int >> 64, ip_int & ((1 << 64) - 1)
