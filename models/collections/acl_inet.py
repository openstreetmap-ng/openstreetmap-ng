from ipaddress import IPv4Network, IPv6Network

from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from models.collections.acl import ACL


class ACLINet(ACL):
    __tablename__ = 'acl_inet'

    inet: Mapped[IPv4Network | IPv6Network] = mapped_column(INET)
