from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from services.cache_service import CACHE_HASH_SIZE
from models.db.base import Base


class CacheEntry(Base.NoID):
    __tablename__ = 'cache'

    id: Mapped[bytes] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=False, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # TODO: prune
    value: Mapped[str] = mapped_column(Unicode, nullable=False)
