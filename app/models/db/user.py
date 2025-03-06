from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Literal, NewType, NotRequired, TypedDict

from shapely import Point

from app.config import DELETED_USER_EMAIL_SUFFIX, TEST_USER_EMAIL_SUFFIX
from app.lib.image import DEFAULT_USER_AVATAR_URL, AvatarType, Image
from app.lib.rich_text import resolve_rich_text
from app.models.scope import Scope
from app.models.types import DisplayName, Email, LocaleCode, StorageKey

UserId = NewType('UserId', int)
UserRole = Literal['moderator', 'administrator']
Editor = Literal['id', 'rapid', 'remote']

DEFAULT_EDITOR: Editor = 'id'


class UserInit(TypedDict):
    email: Email
    email_verified: bool
    display_name: DisplayName
    password_pb: bytes
    language: LocaleCode
    activity_tracking: bool
    crash_reporting: bool
    created_ip: IPv4Address | IPv6Address


class User(UserInit):
    id: UserId
    roles: list[UserRole]
    timezone: str | None
    editor: Editor | None
    home_point: Point | None
    avatar_type: AvatarType
    avatar_id: StorageKey | None
    background_id: StorageKey | None
    description: str
    description_rich_hash: bytes | None
    created_at: datetime
    password_updated_at: datetime | None
    scheduled_delete_at: datetime | None

    # runtime
    description_rich: NotRequired[str]


class UserDisplay(TypedDict):
    """Minimal user information for public display."""

    id: UserId
    display_name: DisplayName
    avatar_type: AvatarType
    avatar_id: StorageKey


async def users_resolve_rich_text(objs: list[User]) -> None:
    await resolve_rich_text(objs, 'user', 'description', 'markdown')


def user_is_test(user: User | UserInit) -> bool:
    """Check if the user is a test user."""
    return user['email'].endswith(TEST_USER_EMAIL_SUFFIX)


def user_is_deleted(user: User | UserInit) -> bool:
    """Check if the user is a deleted user."""
    return user['email'].endswith(DELETED_USER_EMAIL_SUFFIX)


def user_is_moderator(user: User | None) -> bool:
    """Check if the user is a moderator."""
    if user is None:
        return False
    roles = user['roles']
    return 'moderator' in roles or 'administrator' in roles


def user_is_admin(user: User | None) -> bool:
    """Check if the user is an administrator."""
    if user is None:
        return False
    return 'administrator' in user['roles']


def user_extend_scopes(user: User, scopes: tuple[Scope, ...]) -> tuple[Scope, ...]:
    """Extend the given scopes with the user-specific scopes."""
    if not user['roles']:
        return scopes
    extra: list[Scope] = []
    if user_is_moderator(user):
        extra.append('role_moderator')
    if user_is_admin(user):
        extra.append('role_administrator')
    return *scopes, *extra


def user_avatar_url(user: User | UserDisplay) -> str:
    """Get the url for the user's avatar image."""
    avatar_type = user['avatar_type']
    if avatar_type is None:
        return DEFAULT_USER_AVATAR_URL
    if avatar_type == 'gravatar':
        return Image.get_avatar_url('gravatar', user['id'])
    if avatar_type == 'custom':
        avatar_id = user['avatar_id']
        assert avatar_id is not None, 'avatar_id must be set'
        return Image.get_avatar_url('custom', avatar_id)
    raise NotImplementedError(f'Unsupported avatar type {avatar_type!r}')


def user_background_url(user: User) -> str | None:
    """Get the url for the user's background image."""
    return Image.get_background_url(user['background_id'])


# TODO: remove
# # @validates('description')
# # def validate_description(self, _: str, value: str):
# #     if len(value) > USER_DESCRIPTION_MAX_LENGTH:
# #         raise ValueError(f'User description is too long ({len(value)} > {USER_DESCRIPTION_MAX_LENGTH})')
# #     return value


# TODO: remove
# async def home_distance_to(self, point: Point | None) -> float | None:
#     if point is None or self.home_point is None:
#         return None
#     return haversine_distance(self.home_point, point)
