from datetime import datetime
from typing import NewType, NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.db.diary import Diary, DiaryId
from app.models.db.user import UserDisplay, UserId

DiaryCommentId = NewType('DiaryCommentId', int)


class DiaryCommentInit(TypedDict):
    user_id: UserId
    diary_id: DiaryId
    body: str  # TODO: validate size


class DiaryComment(DiaryCommentInit):
    id: DiaryCommentId
    body_rich_hash: bytes | None
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    body_rich: NotRequired[str]
    diary: NotRequired[Diary]


async def diary_comments_resolve_rich_text(objs: list[DiaryComment]) -> None:
    await resolve_rich_text(objs, 'diary_comment', 'body', 'markdown')
