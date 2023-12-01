from collections.abc import Sequence
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from argon2 import PasswordHasher
from shapely.geometry import Point
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    LargeBinary,
    SmallInteger,
    Unicode,
    UnicodeText,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from config import DEFAULT_LANGUAGE
from cython_lib.geoutils import haversine_distance
from lib.avatar import Avatar
from lib.cache import CACHE_HASH_SIZE
from lib.languages import get_language_info, normalize_language_case
from lib.rich_text import rich_text_getter
from limits import (
    LANGUAGE_CODE_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
    USER_LANGUAGES_LIMIT,
)
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.geometry_type import PointType
from models.language_info import LanguageInfo
from models.text_format import TextFormat
from models.user_avatar_type import UserAvatarType
from models.user_role import UserRole
from models.user_status import UserStatus


class User(Base.NoID, CreatedAt):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(BigInteger, nullable=False, primary_key=True)

    email: Mapped[str] = mapped_column(Unicode, nullable=False)
    display_name: Mapped[str] = mapped_column(Unicode, nullable=False)
    password_hashed: Mapped[str] = mapped_column(Unicode, nullable=False)
    created_ip: Mapped[IPv4Address | IPv6Address] = mapped_column(INET, nullable=False)

    consider_public_domain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Unicode(LANGUAGE_CODE_MAX_LENGTH)), nullable=False)

    auth_provider: Mapped[str | None] = mapped_column(Unicode, nullable=True)
    auth_uid: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # defaults
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), nullable=False, default=UserStatus.pending)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password_salt: Mapped[str | None] = mapped_column(Unicode, nullable=True, default=None)
    terms_seen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    roles: Mapped[list[UserRole]] = mapped_column(ARRAY(Enum(UserRole)), nullable=False, default=())
    description: Mapped[str] = mapped_column(UnicodeText, nullable=False, default='')
    description_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None
    )
    description_rich = rich_text_getter('description', TextFormat.markdown)
    home_point: Mapped[Point | None] = mapped_column(PointType, nullable=True, default=None)
    home_zoom: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=None)
    avatar_type: Mapped[UserAvatarType] = mapped_column(
        Enum(UserAvatarType), nullable=False, default=UserAvatarType.default
    )
    avatar_id: Mapped[str | None] = mapped_column(Unicode, nullable=True, default=None)
    # TODO: user preferences

    # relationships (nested imports to avoid circular imports)
    from changeset import Changeset
    from changeset_comment import ChangesetComment
    from diary_comment import DiaryComment
    from friendship import Friendship
    from message import Message
    from note_comment import NoteComment
    from oauth1_application import OAuth1Application
    from oauth1_token import OAuth1Token
    from oauth2_application import OAuth2Application
    from oauth2_token import OAuth2Token
    from trace_ import Trace
    from user_block import UserBlock

    changesets: Mapped[list[Changeset]] = relationship(
        back_populates='user',
        order_by='desc(Changeset.id)',
        lazy='raise',
    )
    changeset_comments: Mapped[list[ChangesetComment]] = relationship(
        back_populates='user',
        order_by='desc(ChangesetComment.created_at)',
        lazy='raise',
    )
    diary_comments: Mapped[list[DiaryComment]] = relationship(
        back_populates='user',
        order_by='desc(DiaryComment.created_at)',
        lazy='raise',
    )
    friendship_sent: Mapped[list['User']] = relationship(
        back_populates='friendship_received',
        secondary=Friendship,
        primaryjoin=id == Friendship.from_user_id,
        secondaryjoin=id == Friendship.to_user_id,
        lazy='raise',
    )
    friendship_received: Mapped[list['User']] = relationship(
        back_populates='friendship_sent',
        secondary=Friendship,
        primaryjoin=id == Friendship.to_user_id,
        secondaryjoin=id == Friendship.from_user_id,
        lazy='raise',
    )
    messages_sent: Mapped[list[Message]] = relationship(
        back_populates='from_user',
        order_by='desc(Message.created_at)',
        lazy='raise',
    )
    messages_received: Mapped[list[Message]] = relationship(
        back_populates='to_user',
        order_by='desc(Message.created_at)',
        lazy='raise',
    )
    note_comments: Mapped[list[NoteComment]] = relationship(
        back_populates='user',
        order_by='desc(NoteComment.created_at)',
        lazy='raise',
    )
    oauth1_applications: Mapped[list[OAuth1Application]] = relationship(
        back_populates='user',
        order_by='asc(OAuth1Application.id)',
        lazy='raise',
    )
    oauth1_tokens: Mapped[list[OAuth1Token]] = relationship(
        back_populates='user',
        order_by='asc(OAuth1Token.application_id)',
        lazy='raise',
    )
    oauth2_applications: Mapped[list[OAuth2Application]] = relationship(
        back_populates='user',
        order_by='asc(OAuth2Application.id)',
        lazy='raise',
    )
    oauth2_tokens: Mapped[list[OAuth2Token]] = relationship(
        back_populates='user',
        order_by='asc(OAuth2Token.application_id)',
        lazy='raise',
    )
    traces: Mapped[list[Trace]] = relationship(
        back_populates='user',
        order_by='desc(Trace.id)',
        lazy='raise',
    )
    user_blocks_given: Mapped[list[UserBlock]] = relationship(
        back_populates='from_user',
        order_by='desc(UserBlock.id)',
        lazy='raise',
    )
    user_blocks_received: Mapped[list[UserBlock]] = relationship(
        back_populates='to_user',
        order_by='desc(UserBlock.id)',
        lazy='raise',
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
    def language_str(self) -> str:
        return ' '.join(self.languages)

    @language_str.setter
    def language_str(self, s: str) -> None:
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
    def password_hasher(self) -> PasswordHasher:
        """
        Get the password hasher for this user.
        """

        return UserRole.get_password_hasher(self.roles)

    @property
    def avatar_url(self) -> str:
        """
        Get the url for the user's avatar image.
        """

        # when using gravatar, use user id as the avatar id
        if self.avatar_type == UserAvatarType.gravatar:
            return Avatar.get_url(self.avatar_type, self.id)
        else:
            return Avatar.get_url(self.avatar_type, self.avatar_id)

    async def home_distance_to(self, point: Point | None) -> float | None:
        return haversine_distance(self.home_point, point) if self.home_point and point else None
