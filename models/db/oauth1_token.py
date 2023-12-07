from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.crypto import HASH_SIZE
from models.db.base import Base
from models.db.created_at_mixin import CreatedAtMixin
from models.db.oauth1_application import OAuth1Application
from models.db.user import User
from models.scope import Scope

# TODO: smooth reauthorize


class OAuth1Token(Base.UUID, CreatedAtMixin):
    __tablename__ = 'oauth1_token'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='joined')
    application_id: Mapped[int] = mapped_column(ForeignKey(OAuth1Application.id), nullable=False)
    application: Mapped[OAuth1Application] = relationship(back_populates='oauth1_tokens', lazy='joined')
    token_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)  # TODO: binary length
    # token_secret encryption is redundant, key is already hashed
    token_secret: Mapped[bytes] = mapped_column(LargeBinary(40), nullable=False)
    scopes: Mapped[list[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Unicode, nullable=True)
    verifier: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # defaults
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    @property
    def is_oob(self) -> bool:
        return not self.callback_url
