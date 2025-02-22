from collections.abc import Iterable
from datetime import datetime
from typing import NewType, NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.db.diary import DiaryId
from app.models.db.user import User, UserId

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
    user: NotRequired[User]
    body_rich: NotRequired[str]


async def changeset_comments_resolve_rich_text(objs: Iterable[DiaryComment]) -> None:
    await resolve_rich_text(objs, 'diary_comment', 'body', 'markdown')
