import tomllib
from pathlib import Path
from typing import NotRequired, TypedDict

from app.models.db.user_profile import USER_SOCIAL_TYPES, UserSocialType


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
