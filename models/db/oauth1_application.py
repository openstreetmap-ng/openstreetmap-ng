from typing import Self

from sqlalchemy import ARRAY, Enum, ForeignKey, LargeBinary, Sequence, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.crypto import decrypt_b
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.scope import Scope
from utils import updating_cached_property

# TODO: cascading delete
# TODO: move validation logic

class OAuth1Application(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'oauth1_application'

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(back_populates='oauth1_applications', lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)  # TODO: limit size
    consumer_key: Mapped[str] = mapped_column(Unicode(40), nullable=False)
    consumer_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[Sequence[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    application_url: Mapped[str] = mapped_column(Unicode, nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    @updating_cached_property(lambda self: self.consumer_secret_encrypted)
    def consumer_secret(self) -> str:
        return decrypt_b(self.consumer_secret_encrypted)

    # TODO: SQL
    @classmethod
    async def find_one_by_key(cls, key: str) -> Self | None:
        return await cls.find_one({'key_public': key})
