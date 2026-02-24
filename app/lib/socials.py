import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import NotRequired, TypedDict

from app.models.db.user_profile import USER_SOCIAL_TYPES, UserSocial, UserSocialType
from app.models.proto.shared_pb2 import UserSocial as ProtoUserSocial


class SocialConfig(TypedDict):
    icon: NotRequired[str]
    label: str
    placeholder: str
    template: NotRequired[str]


SOCIALS_CONFIG: dict[UserSocialType, SocialConfig]
SOCIALS_CONFIG = tomllib.loads(Path('config/socials.toml').read_text())  # type: ignore

current = frozenset(SOCIALS_CONFIG)
if current != USER_SOCIAL_TYPES:
    extra = sorted(current - USER_SOCIAL_TYPES)
    missing = sorted(USER_SOCIAL_TYPES - current)
    raise AssertionError(f'socials config mismatch ({extra=}, {missing=})')


def user_socials(socials: Iterable[ProtoUserSocial]):
    result: list[UserSocial] = []

    for social in socials:
        social_type: UserSocialType = social.service  # type: ignore
        config = SOCIALS_CONFIG.get(social_type)
        if config is None:
            continue

        value = social.value.strip()
        if not value:
            continue

        if 'template' not in config and not value.lower().startswith('https://'):
            value = 'https://' + value.split('://', 1)[-1]

        result.append(UserSocial(social_type, value))

    return result
