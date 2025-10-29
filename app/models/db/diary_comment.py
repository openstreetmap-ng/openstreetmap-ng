from datetime import datetime
from typing import NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text_with_proxy
from app.models.db.diary import Diary
from app.models.db.user import UserDisplay
from app.models.types import DiaryCommentId, DiaryId, UserId


class DiaryCommentInit(TypedDict):
    id: DiaryCommentId
    user_id: UserId
    diary_id: DiaryId
    body: str  # TODO: validate size


class DiaryComment(DiaryCommentInit):
    body_rich_hash: bytes | None
    image_proxy_ids: list[int] | None
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    body_rich: NotRequired[str]
    diary: NotRequired[Diary]


async def diary_comments_resolve_rich_text(objs: list[DiaryComment]) -> None:
    await resolve_rich_text_with_proxy(objs, 'diary_comment', 'body', 'markdown')
