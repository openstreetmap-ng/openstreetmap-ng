from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, Enum, ForeignKey, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.crypto import decrypt
from app.lib.updating_cached_property import updating_cached_property
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.oauth2_application_type import OAuth2ApplicationType
from app.models.scope import Scope


class OAuth2Application(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'oauth2_application'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='oauth2_applications', lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)
    client_id: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    client_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[list[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    type: Mapped[OAuth2ApplicationType] = mapped_column(Enum(OAuth2ApplicationType), nullable=False)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Unicode), nullable=False)

    # relationships (avoid circular imports)
    if TYPE_CHECKING:
        from app.models.db.oauth2_token import OAuth2Token

    oauth2_tokens: Mapped[list['OAuth2Token']] = relationship(
        back_populates='application',
        lazy='raise',
    )

    @updating_cached_property('client_secret_encrypted')
    def client_secret(self) -> str:
        return decrypt(self.client_secret_encrypted)
