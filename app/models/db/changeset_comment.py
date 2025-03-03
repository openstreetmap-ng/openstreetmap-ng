from datetime import datetime
from typing import NewType, NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.db.changeset import ChangesetId
from app.models.db.user import UserDisplay, UserId

ChangesetCommentId = NewType('ChangesetCommentId', int)


class ChangesetCommentInit(TypedDict):
    user_id: UserId
    changeset_id: ChangesetId
    body: str  # TODO: validate size


class ChangesetComment(ChangesetCommentInit):
    id: ChangesetCommentId
    body_rich_hash: bytes | None
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    body_rich: NotRequired[str]


async def changeset_comments_resolve_rich_text(objs: list[ChangesetComment]) -> None:
    await resolve_rich_text(objs, 'changeset_comment', 'body', 'plain')
