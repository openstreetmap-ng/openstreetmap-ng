from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from models.collections.base import Base


class CacheEntry(Base.NoID):
    __tablename__ = 'cache'

    id: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)  # TODO: prune
    value: Mapped[str] = mapped_column(Unicode)
