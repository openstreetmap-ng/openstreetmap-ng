from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.acl import ACL


class ACLMX(ACL):
    __tablename__ = 'acl_mx'

    mx: Mapped[str] = mapped_column(Unicode, nullable=False)
