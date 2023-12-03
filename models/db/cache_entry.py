from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column

from models.db.base import Base
from services.cache_service import CACHE_HASH_SIZE


class CacheEntry(Base.NoID):
    __tablename__ = 'cache'

    id: Mapped[bytes] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=False, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # TODO: pruner
    value: Mapped[str] = mapped_column(UnicodeText, nullable=False)
