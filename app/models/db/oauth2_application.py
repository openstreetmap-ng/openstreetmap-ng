from sqlalchemy import ARRAY, Boolean, Enum, ForeignKey, Index, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.crypto import decrypt
from app.lib.updating_cached_property import updating_cached_property
from app.limits import OAUTH_APP_NAME_MAX_LENGTH, OAUTH_APP_URI_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.scope import Scope


class OAuth2Application(Base.ZID, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'oauth2_application'

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(init=False, lazy='raise')
    name: Mapped[str] = mapped_column(Unicode(OAUTH_APP_NAME_MAX_LENGTH), nullable=False)
    client_id: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    client_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[tuple[Scope, ...]] = mapped_column(ARRAY(Enum(Scope), as_tuple=True, dimensions=1), nullable=False)
    is_confidential: Mapped[bool] = mapped_column(Boolean, nullable=False)
    redirect_uris: Mapped[list[str]] = mapped_column(
        ARRAY(Unicode(OAUTH_APP_URI_MAX_LENGTH), dimensions=1), nullable=False
    )

    __table_args__ = (Index('oauth2_application_client_id_idx', 'client_id', unique=True),)

    @updating_cached_property('client_secret_encrypted')
    def client_secret(self) -> str:
        return decrypt(self.client_secret_encrypted)
