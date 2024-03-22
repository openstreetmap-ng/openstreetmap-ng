from sqlalchemy import ARRAY, Boolean, Enum, ForeignKey, Index, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.crypto import decrypt
from app.lib.updating_cached_property import updating_cached_property
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.scope import Scope


class OAuth2Application(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'oauth2_application'

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)
    client_id: Mapped[str] = mapped_column(Unicode(50), nullable=False)
    client_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[list[Scope]] = mapped_column(ARRAY(Enum(Scope), dimensions=1), nullable=False)
    is_confidential: Mapped[bool] = mapped_column(Boolean, nullable=False)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Unicode, dimensions=1), nullable=False)

    __table_args__ = (Index('client_id_idx', 'client_id', unique=True),)

    @updating_cached_property('client_secret_encrypted')
    def client_secret(self) -> str:
        return decrypt(self.client_secret_encrypted)
