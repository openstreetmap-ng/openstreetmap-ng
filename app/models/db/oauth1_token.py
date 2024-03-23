from datetime import datetime

from sqlalchemy import ARRAY, Enum, ForeignKey, LargeBinary, Unicode
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.crypto import HASH_SIZE
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.oauth1_application import OAuth1Application
from app.models.db.user import User
from app.models.scope import Scope

# TODO: smooth reauthorize


class OAuth1Token(Base.UUID, CreatedAtMixin):
    __tablename__ = 'oauth1_token'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='joined', innerjoin=True)
    application_id: Mapped[int] = mapped_column(ForeignKey(OAuth1Application.id), nullable=False)
    application: Mapped[OAuth1Application] = relationship(lazy='joined', innerjoin=True)
    token_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)  # TODO: binary length
    # token_secret encryption is redundant, key is already hashed
    token_secret: Mapped[bytes] = mapped_column(LargeBinary(40), nullable=False)
    scopes: Mapped[list[Scope]] = mapped_column(ARRAY(Enum(Scope), dimensions=1), nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Unicode, nullable=True)
    verifier: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # defaults
    authorized_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(True), nullable=True, server_default=None)

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    @property
    def is_oob(self) -> bool:
        return not self.callback_url
