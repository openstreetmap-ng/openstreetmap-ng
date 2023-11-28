from abc import ABC

from sqlalchemy import ARRAY, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from models.db.base import Base


class ACL(Base.UUID, ABC):
    restrictions: Mapped[list[str]] = mapped_column(ARRAY(Unicode), nullable=False)
