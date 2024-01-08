from sqlalchemy import ARRAY, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from src.models.db.base import Base


class ACL(Base.UUID):
    __abstract__ = True

    restrictions: Mapped[list[str]] = mapped_column(ARRAY(Unicode), nullable=False)
