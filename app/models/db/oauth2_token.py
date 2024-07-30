from datetime import datetime

from sqlalchemy import ARRAY, Enum, ForeignKey, Index, LargeBinary, Unicode
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.crypto import HASH_SIZE
from app.limits import OAUTH2_CODE_CHALLENGE_MAX_LENGTH, OAUTH_APP_URI_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import User
from app.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from app.models.scope import Scope


class OAuth2Token(Base.ZID, CreatedAtMixin):
    __tablename__ = 'oauth2_token'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(init=False, lazy='raise', innerjoin=True)
    application_id: Mapped[int] = mapped_column(ForeignKey(OAuth2Application.id, ondelete='CASCADE'), nullable=False)
    application: Mapped[OAuth2Application] = relationship(init=False, lazy='raise', innerjoin=True)
    token_hashed: Mapped[bytes] = mapped_column(LargeBinary(HASH_SIZE), nullable=False)
    scopes: Mapped[tuple[Scope, ...]] = mapped_column(ARRAY(Enum(Scope), as_tuple=True, dimensions=1), nullable=False)
    redirect_uri: Mapped[str | None] = mapped_column(Unicode(OAUTH_APP_URI_MAX_LENGTH), nullable=True)
    code_challenge_method: Mapped[OAuth2CodeChallengeMethod | None] = mapped_column(
        Enum(OAuth2CodeChallengeMethod), nullable=True
    )
    code_challenge: Mapped[str | None] = mapped_column(Unicode(OAUTH2_CODE_CHALLENGE_MAX_LENGTH), nullable=True)

    # defaults
    authorized_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=True,
        server_default=None,
    )

    __table_args__ = (
        Index('oauth2_token_hashed_idx', token_hashed),
        Index('oauth2_token_user_app_idx', user_id, application_id),
    )

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    @property
    def is_oob(self) -> bool:
        return self.redirect_uri in {'urn:ietf:wg:oauth:2.0:oob', 'urn:ietf:wg:oauth:2.0:oob:auto'}
