from ipaddress import IPv4Network, IPv6Network

from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from models.collections.acl import ACL


class ACLINet(ACL):
    __tablename__ = 'acl_inet'

    # TODO: check return type without /mask
    inet: Mapped[IPv4Network | IPv6Network] = mapped_column(INET, nullable=False)
