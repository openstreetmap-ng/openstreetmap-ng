from datetime import datetime
from typing import Literal, NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.db.user import UserDisplay, UserRole
from app.models.types import (
    ApplicationId,
    ChangesetId,
    DiaryId,
    MessageId,
    NoteId,
    ReportCommentId,
    ReportId,
    TraceId,
    UserId,
)

ReportAction = Literal[
    'comment',
    'close',
    'reopen',
    'generic',
    'user_account',
    'user_changeset',
    'user_diary',
    'user_message',
    'user_note',
    'user_oauth2_application',
    'user_profile',
    'user_trace',
]
ReportActionId = (
    ChangesetId | DiaryId | MessageId | NoteId | ApplicationId | UserId | TraceId | None
)

ReportCategory = Literal[
    'spam',
    'vandalism',
    'harassment',
    'privacy',
    'other',
]


class ReportCommentInit(TypedDict):
    id: ReportCommentId
    report_id: ReportId
    user_id: UserId
    action: ReportAction
    action_id: ReportActionId
    body: str  # TODO: validate size
    category: ReportCategory | None
    visible_to: UserRole


class ReportComment(ReportCommentInit):
    body_rich_hash: bytes | None
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    body_rich: NotRequired[str]
    is_restricted: NotRequired[bool]


async def report_comments_resolve_rich_text(objs: list[ReportComment]) -> None:
    await resolve_rich_text(objs, 'report_comment', 'body', 'plain')
