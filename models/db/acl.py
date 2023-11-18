from abc import ABC
from collections.abc import Sequence

from sqlalchemy import ARRAY, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from models.db.base import Base


class ACL(Base.UUID, ABC):
    restrictions: Mapped[Sequence[str]] = mapped_column(ARRAY(Unicode), nullable=False)
