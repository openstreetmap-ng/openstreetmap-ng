from ipaddress import IPv4Address, IPv4Network

from models.collections.acl import ACL


class ACLIPv4(ACL):
    ipv4_min: int
    ipv4_max: int

    @staticmethod
    def net_to_int(net: IPv4Network) -> tuple[int, int]:
        return int(net.network_address), int(net.broadcast_address)

    @staticmethod
    def ip_to_int(ip: IPv4Address) -> int:
        return int(ip)
