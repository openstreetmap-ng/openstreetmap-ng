from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, Enum, ForeignKey, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.libc.crypto import decrypt
from app.libc.updating_cached_property import updating_cached_property
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.scope import Scope

# TODO: cascading delete
# TODO: move validation logic
# TODO: OAUTH_APP_NAME_MAX_LENGTH


class OAuth1Application(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'oauth1_application'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='oauth1_applications', lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)
    consumer_key: Mapped[str] = mapped_column(Unicode(40), nullable=False)
    consumer_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[list[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    application_url: Mapped[str] = mapped_column(Unicode, nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # relationships (avoid circular imports)
    if TYPE_CHECKING:
        from oauth1_token import OAuth1Token

    oauth1_tokens: Mapped[list['OAuth1Token']] = relationship(
        back_populates='application',
        lazy='raise',
    )

    @updating_cached_property('consumer_secret_encrypted')
    def consumer_secret(self) -> str:
        return decrypt(self.consumer_secret_encrypted)
