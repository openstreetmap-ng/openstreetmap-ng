from ipaddress import IPv4Network, IPv6Network

from sqlalchemy.dialects.postgresql import CIDR
from sqlalchemy.orm import Mapped, mapped_column

from models.db.acl import ACL


class ACLINet(ACL):
    __tablename__ = 'acl_inet'

    inet: Mapped[IPv4Network | IPv6Network] = mapped_column(CIDR, nullable=False)
