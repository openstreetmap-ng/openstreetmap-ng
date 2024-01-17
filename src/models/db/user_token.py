from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from src.lib_cython.crypto import HASH_SIZE
from src.models.db.base import Base
from src.models.db.created_at_mixin import CreatedAtMixin
from src.models.db.user import User


class UserToken(Base.UUID, CreatedAtMixin):
    __abstract__ = True

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    token_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @declared_attr
    @classmethod
    def user(cls) -> Mapped[User]:
        return relationship(User, lazy='joined')
