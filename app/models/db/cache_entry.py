from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column

from app.libc.crypto import HASH_SIZE
from app.models.db.base import Base


class CacheEntry(Base.NoID):
    __tablename__ = 'cache'

    id: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # TODO: pruner
    value: Mapped[str] = mapped_column(UnicodeText, nullable=False)
