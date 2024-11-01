import enum
from datetime import datetime
from typing import override

from sqlalchemy import ARRAY, Enum, ForeignKey, Index, LargeBinary, Unicode, null
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.crypto import HASH_SIZE
from app.limits import (
    OAUTH_APP_URI_MAX_LENGTH,
    OAUTH_CODE_CHALLENGE_MAX_LENGTH,
    OAUTH_PAT_NAME_MAX_LENGTH,
    OAUTH_SECRET_PREVIEW_LENGTH,
)
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import User
from app.models.scope import Scope
from app.models.types import Uri


class OAuth2ResponseType(str, enum.Enum):
    code = 'code'


class OAuth2ResponseMode(str, enum.Enum):
    query = 'query'
    fragment = 'fragment'
    form_post = 'form_post'


class OAuth2GrantType(str, enum.Enum):
    authorization_code = 'authorization_code'


class OAuth2CodeChallengeMethod(str, enum.Enum):
    plain = 'plain'
    S256 = 'S256'


class OAuth2TokenEndpointAuthMethod(str, enum.Enum):
    client_secret_post = 'client_secret_post'  # noqa: S105
    client_secret_basic = 'client_secret_basic'  # noqa: S105


class OAuth2TokenOOB:
    __slots__ = ('authorization_code', 'state')

    def __init__(self, authorization_code: str, state: str | None) -> None:
        self.authorization_code = authorization_code
        self.state = state

    @override
    def __str__(self) -> str:
        return self.authorization_code if (self.state is None) else f'{self.authorization_code}#{self.state}'


class OAuth2Token(Base.ZID, CreatedAtMixin):
    __tablename__ = 'oauth2_token'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(init=False, lazy='raise', innerjoin=True)
    application_id: Mapped[int] = mapped_column(ForeignKey(OAuth2Application.id, ondelete='CASCADE'), nullable=False)
    application: Mapped[OAuth2Application] = relationship(init=False, lazy='raise', innerjoin=True)
    token_hashed: Mapped[bytes | None] = mapped_column(LargeBinary(HASH_SIZE), nullable=True)
    scopes: Mapped[tuple[Scope, ...]] = mapped_column(ARRAY(Enum(Scope), as_tuple=True, dimensions=1), nullable=False)
    redirect_uri: Mapped[Uri | None] = mapped_column(Unicode(OAUTH_APP_URI_MAX_LENGTH), nullable=True)
    code_challenge_method: Mapped[OAuth2CodeChallengeMethod | None] = mapped_column(
        Enum(OAuth2CodeChallengeMethod), nullable=True
    )
    code_challenge: Mapped[str | None] = mapped_column(Unicode(OAUTH_CODE_CHALLENGE_MAX_LENGTH), nullable=True)

    # defaults
    authorized_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=True,
        server_default=None,
    )

    # PATs
    name: Mapped[str | None] = mapped_column(
        Unicode(OAUTH_PAT_NAME_MAX_LENGTH),
        init=False,
        nullable=True,
        server_default=None,
    )
    token_preview: Mapped[str | None] = mapped_column(
        Unicode(OAUTH_SECRET_PREVIEW_LENGTH),
        init=False,
        nullable=True,
        server_default=None,
    )

    __table_args__ = (
        Index(
            'oauth2_token_hashed_idx',
            token_hashed,
            postgresql_where=token_hashed != null(),
        ),
        Index(
            'oauth2_token_authorized_user_app_idx',
            user_id,
            application_id,
            postgresql_where=authorized_at != null(),
        ),
        Index(
            'oauth2_token_unauthorized_user_app_idx',
            user_id,
            application_id,
            postgresql_where=authorized_at == null(),
        ),
    )

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    @property
    def is_oob(self) -> bool:
        return self.redirect_uri in {'urn:ietf:wg:oauth:2.0:oob', 'urn:ietf:wg:oauth:2.0:oob:auto'}
