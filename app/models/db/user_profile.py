from typing import Literal, NamedTuple, NotRequired, TypedDict, get_args

from app.lib.rich_text import resolve_rich_text
from app.models.types import UserId

UserSocialType = Literal[
    'bluesky',
    'discord',
    'facebook',
    'github',
    'instagram',
    'line',
    'linkedin',
    'mastodon',
    'medium',
    'pinterest',
    'reddit',
    'signal',
    'sina-weibo',
    'snapchat',
    'spotify',
    'steam',
    'telegram',
    'threads',
    'tiktok',
    'twitch',
    'wechat',
    'whatsapp',
    'wordpress',
    'x',
    'youtube',
    'other',
]

USER_SOCIAL_TYPES = frozenset[UserSocialType](get_args(UserSocialType))


class UserSocial(NamedTuple):
    service: UserSocialType
    value: str


class UserProfile(TypedDict):
    user_id: UserId
    description: str | None
    description_rich_hash: bytes | None
    socials: list[UserSocial]

    # runtime
    description_rich: NotRequired[str]


async def user_profiles_resolve_rich_text(objs: list[UserProfile]):
    await resolve_rich_text(
        objs,
        'user_profile',
        'description',
        'markdown',
        pk_field='user_id',
    )
