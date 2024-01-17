from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.libc.crypto import HASH_SIZE
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import User
from app.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from app.models.scope import Scope


class OAuth2Token(Base.UUID, CreatedAtMixin):
    __tablename__ = 'oauth2_token'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='joined')
    application_id: Mapped[int] = mapped_column(ForeignKey(OAuth2Application.id), nullable=False)
    application: Mapped[OAuth2Application] = relationship(back_populates='oauth2_tokens', lazy='joined')
    token_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)
    scopes: Mapped[list[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Unicode, nullable=False)
    code_challenge_method: Mapped[OAuth2CodeChallengeMethod | None] = mapped_column(
        Enum(OAuth2CodeChallengeMethod), nullable=True
    )
    code_challenge: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # defaults
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    @property
    def is_oob(self) -> bool:
        return self.redirect_uri in ('urn:ietf:wg:oauth:2.0:oob', 'urn:ietf:wg:oauth:2.0:oob:auto')
