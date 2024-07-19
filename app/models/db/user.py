from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import TYPE_CHECKING

from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from shapely import Point
from sqlalchemy import (
    ARRAY,
    Boolean,
    Enum,
    Index,
    LargeBinary,
    Unicode,
    UnicodeText,
    func,
    or_,
)
from sqlalchemy.dialects.postgresql import INET, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.avatar import Avatar
from app.lib.crypto import HASH_SIZE
from app.lib.geo_utils import haversine_distance
from app.lib.rich_text import RichTextMixin
from app.lib.storage.base import STORAGE_KEY_MAX_LENGTH, StorageKey
from app.limits import (
    DISPLAY_NAME_MAX_LENGTH,
    LANGUAGE_CODE_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
)
from app.models.auth_provider import AuthProvider
from app.models.avatar_type import AvatarType
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.editor import Editor
from app.models.geometry import PointType
from app.models.scope import Scope
from app.models.text_format import TextFormat
from app.models.user_role import UserRole
from app.models.user_status import UserStatus

if TYPE_CHECKING:
    from app.models.db.user_block import UserBlock


class User(Base.Sequential, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'user'
    __rich_text_fields__ = (('description', TextFormat.markdown),)

    email: Mapped[str] = mapped_column(Unicode(EMAIL_MAX_LENGTH), nullable=False)
    display_name: Mapped[str] = mapped_column(Unicode(DISPLAY_NAME_MAX_LENGTH), nullable=False)
    password_hashed: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    created_ip: Mapped[IPv4Address | IPv6Address] = mapped_column(INET, nullable=False)

    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), nullable=False)

    auth_provider: Mapped[AuthProvider | None] = mapped_column(Enum(AuthProvider), nullable=True)
    auth_uid: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    language: Mapped[str] = mapped_column(Unicode(LANGUAGE_CODE_MAX_LENGTH), nullable=False)
    activity_tracking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    crash_reporting: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # defaults
    password_changed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=True,
        server_default=func.statement_timestamp(),
    )
    roles: Mapped[tuple[UserRole, ...]] = mapped_column(
        ARRAY(Enum(UserRole), as_tuple=True, dimensions=1),
        init=False,
        nullable=False,
        server_default='{}',
    )
    description: Mapped[str] = mapped_column(
        UnicodeText,
        init=False,
        nullable=False,
        server_default='',
    )
    description_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )
    description_rich: str | None = None
    editor: Mapped[Editor | None] = mapped_column(
        Enum(Editor),
        init=False,
        nullable=True,
        server_default=None,
    )
    avatar_type: Mapped[AvatarType] = mapped_column(
        Enum(AvatarType),
        init=False,
        nullable=False,
        server_default=AvatarType.default.value,
    )
    avatar_id: Mapped[StorageKey | None] = mapped_column(
        Unicode(STORAGE_KEY_MAX_LENGTH),
        init=False,
        nullable=True,
        server_default=None,
    )
    home_point: Mapped[Point | None] = mapped_column(
        PointType,
        init=False,
        nullable=True,
        server_default=None,
    )

    # relationships (avoid circular imports)
    active_user_blocks_received: Mapped[list['UserBlock']] = relationship(
        back_populates='to_user',
        order_by='UserBlock.id.desc()',
        lazy='raise',
        primaryjoin='and_(UserBlock.to_user_id == User.id, UserBlock.expired == false())',
        viewonly=True,
        init=False,
    )

    __table_args__ = (
        Index('user_email_idx', email, unique=True),
        Index('user_display_name_idx', display_name, unique=True),
        Index(
            'user_pending_idx',
            'created_at',
            postgresql_where=or_(
                status == UserStatus.pending_activation,
                status == UserStatus.pending_terms,
            ),
        ),
    )

    @validates('description')
    def validate_description(self, _: str, value: str):
        if len(value) > USER_DESCRIPTION_MAX_LENGTH:
            raise ValueError(f'User description is too long ({len(value)} > {USER_DESCRIPTION_MAX_LENGTH})')
        return value

    @property
    def is_administrator(self) -> bool:
        """
        Check if the user is an administrator.
        """
        return UserRole.administrator in self.roles

    @property
    def is_moderator(self) -> bool:
        """
        Check if the user is a moderator.
        """
        return UserRole.moderator in self.roles or self.is_administrator

    def extend_scopes(self, scopes: tuple[Scope, ...]) -> tuple[Scope, ...]:
        """
        Extend the scopes with user-specific scopes.
        """
        if not self.roles:
            return scopes
        extra: list[Scope] = []
        if self.is_administrator:
            extra.append(Scope.role_administrator)
        if self.is_moderator:
            extra.append(Scope.role_moderator)
        return (*scopes, *extra)

    @property
    def avatar_url(self) -> str:
        """
        Get the url for the user's avatar image.
        """
        # when using gravatar, use user id as the avatar id
        if self.avatar_type == AvatarType.gravatar:
            return Avatar.get_url(self.avatar_type, self.id)
        else:
            return Avatar.get_url(self.avatar_type, self.avatar_id)

    async def home_distance_to(self, point: Point | None) -> float | None:
        if point is None or self.home_point is None:
            return None

        return haversine_distance(self.home_point, point)
