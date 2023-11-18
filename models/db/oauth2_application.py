from sqlalchemy import ARRAY, Enum, ForeignKey, LargeBinary, Sequence, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.crypto import decrypt_b
from lib.updating_cached_property import updating_cached_property
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.oauth2_application_type import OAuth2ApplicationType
from models.scope import Scope

# TODO: cascading delete
# TODO: move validation logic


class OAuth2Application(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'oauth2_application'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='oauth2_applications', lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)
    client_id: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    client_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[Sequence[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    type: Mapped[OAuth2ApplicationType] = mapped_column(Enum(OAuth2ApplicationType), nullable=False)
    redirect_uris: Mapped[Sequence[str]] = mapped_column(ARRAY(Unicode), nullable=False)

    # relationships (nested imports to avoid circular imports)
    from oauth2_token import OAuth2Token

    oauth2_tokens: Mapped[Sequence[OAuth2Token]] = relationship(
        back_populates='application',
        lazy='raise',
    )

    @updating_cached_property('client_secret_encrypted')
    def client_secret(self) -> str:
        return decrypt_b(self.client_secret_encrypted)
