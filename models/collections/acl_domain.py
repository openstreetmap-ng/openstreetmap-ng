from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from models.collections.acl import ACL


class ACLDomain(ACL):
    __tablename__ = 'acl_domain'

    domain: Mapped[str] = mapped_column(Unicode, nullable=False)
