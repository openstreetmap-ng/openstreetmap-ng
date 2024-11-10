from sqlalchemy import Enum, ForeignKey, Index, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from app.limits import AUTH_PROVIDER_UID_MAX_LENGTH
from app.models.auth_provider import AuthProvider
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.user import User


class ConnectedAccount(Base.ZID, CreatedAtMixin):
    __tablename__ = 'connected_account'

    provider: Mapped[AuthProvider] = mapped_column(Enum(AuthProvider), nullable=False)
    uid: Mapped[str] = mapped_column(Unicode(AUTH_PROVIDER_UID_MAX_LENGTH), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)

    __table_args__ = (
        Index('connected_account_provider_uid_idx', provider, uid, unique=True),
        Index('connected_account_user_provider_idx', user_id, provider, unique=True, postgresql_include=('id',)),
    )
