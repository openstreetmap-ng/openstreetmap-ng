from typing import NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.types import UserId


class UserProfile(TypedDict):
    user_id: UserId
    description: str
    description_rich_hash: bytes | None

    # runtime
    description_rich: NotRequired[str]


async def user_profiles_resolve_rich_text(objs: list[UserProfile]) -> None:
    await resolve_rich_text(objs, 'user_profile', 'description', 'markdown')  # type: ignore
