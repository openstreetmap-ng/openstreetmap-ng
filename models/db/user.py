from collections.abc import Sequence
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import TYPE_CHECKING

from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from shapely.geometry import Point
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    LargeBinary,
    SmallInteger,
    Unicode,
    UnicodeText,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from config import APP_URL, DEFAULT_LANGUAGE
from cython_lib.geo_utils import haversine_distance
from lib.avatar import Avatar
from lib.crypto import HASH_SIZE
from lib.languages import get_language_info, normalize_language_case
from lib.password_hash import PasswordHash
from lib.rich_text import RichTextMixin
from lib.storage.base import STORAGE_KEY_MAX_LENGTH
from limits import (
    LANGUAGE_CODE_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
    USER_LANGUAGES_LIMIT,
)
from models.auth_provider import AuthProvider
from models.avatar_type import AvatarType
from models.db.base import Base
from models.db.cache_entry import CacheEntry
from models.db.created_at_mixin import CreatedAtMixin
from models.editor import Editor
from models.geometry_type import PointType
from models.language_info import LanguageInfo
from models.scope import ExtendedScope
from models.text_format import TextFormat
from models.user_role import UserRole
from models.user_status import UserStatus


class User(Base.Sequential, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'user'
    __rich_text_fields__ = (('description', TextFormat.markdown),)

    email: Mapped[str] = mapped_column(Unicode(EMAIL_MAX_LENGTH), nullable=False)
    display_name: Mapped[str] = mapped_column(Unicode, nullable=False)
    password_hashed: Mapped[str] = mapped_column(Unicode, nullable=False)
    created_ip: Mapped[IPv4Address | IPv6Address] = mapped_column(INET, nullable=False)

    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), nullable=False)

    auth_provider: Mapped[AuthProvider | None] = mapped_column(Enum(AuthProvider), nullable=True)
    auth_uid: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    languages: Mapped[list[str]] = mapped_column(ARRAY(Unicode(LANGUAGE_CODE_MAX_LENGTH)), nullable=False)

    # defaults
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=func.now())
    password_salt: Mapped[str | None] = mapped_column(Unicode, nullable=True, default=None)
    consider_public_domain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    roles: Mapped[list[UserRole]] = mapped_column(ARRAY(Enum(UserRole)), nullable=False, default=())
    description: Mapped[str] = mapped_column(UnicodeText, nullable=False, default='')
    description_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(HASH_SIZE), nullable=True, default=None)
    description_rich: Mapped[CacheEntry | None] = relationship(
        CacheEntry,
        primaryjoin=CacheEntry.id == description_rich_hash,
        viewonly=True,
        default=None,
        lazy='raise',
    )
    editor: Mapped[Editor | None] = mapped_column(Enum(Editor), nullable=True, default=None)
    avatar_type: Mapped[AvatarType] = mapped_column(Enum(AvatarType), nullable=False, default=AvatarType.default)
    avatar_id: Mapped[str | None] = mapped_column(Unicode(STORAGE_KEY_MAX_LENGTH), nullable=True, default=None)
    home_point: Mapped[Point | None] = mapped_column(PointType, nullable=True, default=None)
    home_zoom: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=None)

    # relationships (avoid circular imports)
    if TYPE_CHECKING:
        from models.db.oauth1_application import OAuth1Application
        from models.db.oauth2_application import OAuth2Application
        from models.db.user_block import UserBlock

    oauth1_applications: Mapped[list['OAuth1Application']] = relationship(
        back_populates='user',
        order_by='OAuth1Application.id.asc()',
        lazy='raise',
    )
    oauth2_applications: Mapped[list['OAuth2Application']] = relationship(
        back_populates='user',
        order_by='OAuth2Application.id.asc()',
        lazy='raise',
    )
    user_blocks_given: Mapped[list['UserBlock']] = relationship(
        back_populates='from_user',
        order_by='UserBlock.id.desc()',
        lazy='raise',
    )
    user_blocks_received: Mapped[list['UserBlock']] = relationship(
        back_populates='to_user',
        order_by='UserBlock.id.desc()',
        lazy='raise',
    )
    active_user_blocks_received: Mapped[list['UserBlock']] = relationship(
        back_populates='to_user',
        order_by='UserBlock.id.desc()',
        lazy='raise',
        primaryjoin='and_(UserBlock.to_user_id == User.id, UserBlock.expired == false())',
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint(email),
        UniqueConstraint(display_name),
    )

    @validates('languages')
    def validate_languages(self, _: str, value: Sequence[str]):
        if len(value) > USER_LANGUAGES_LIMIT:
            raise ValueError('Too many languages')
        return value

    @validates('description')
    def validate_description(self, _: str, value: str):
        if len(value) > USER_DESCRIPTION_MAX_LENGTH:
            raise ValueError('Description is too long')
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

    @property
    def extended_scopes(self) -> Sequence[ExtendedScope]:
        """
        Get the user's extended scopes.
        """

        result = []

        # role-specific scopes
        if self.is_administrator:
            result.append(ExtendedScope.role_administrator)
        if self.is_moderator:
            result.append(ExtendedScope.role_moderator)

        return result

    @property
    def permalink(self) -> str:
        """
        Get the user's permalink.

        >>> user.permalink
        'https://www.openstreetmap.org/user/permalink/123456'
        """

        return f'{APP_URL}/user/permalink/{self.id}'

    @property
    def languages_str(self) -> str:
        return ' '.join(self.languages)

    @languages_str.setter
    def languages_str(self, s: str) -> None:
        languages = s.split()
        languages = (t.strip()[:LANGUAGE_CODE_MAX_LENGTH].strip() for t in languages)
        languages = (normalize_language_case(t) for t in languages)
        languages = (t for t in languages if t)
        self.languages = tuple(set(languages))

    @property
    def preferred_diary_language(self) -> LanguageInfo:
        """
        Get the user's preferred diary language.
        """

        # return the first valid language
        for code in self.languages:
            if lang := get_language_info(code):
                return lang

        # fallback to default
        return get_language_info(DEFAULT_LANGUAGE)

    @property
    def changeset_max_size(self) -> int:
        """
        Get the maximum changeset size for this user.
        """

        return UserRole.get_changeset_max_size(self.roles)

    @property
    def password_hasher(self) -> PasswordHash:
        """
        Get the password hash class for this user.
        """

        return PasswordHash(UserRole.get_password_hasher(self.roles))

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
        return haversine_distance(self.home_point, point) if self.home_point and point else None
