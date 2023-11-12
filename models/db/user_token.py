from abc import ABC
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.crypto import HASH_SIZE
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.user import User


class UserToken(Base.UUID, CreatedAt, ABC):
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    key_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
