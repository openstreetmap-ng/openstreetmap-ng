from datetime import datetime
from typing import Literal, NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.db.diary import Diary
from app.models.db.message import Message
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.trace import Trace
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
    object: NotRequired[Diary | Message | OAuth2Application | Trace]
    body_rich: NotRequired[str]
    has_access: NotRequired[bool]


async def report_comments_resolve_rich_text(objs: list[ReportComment]):
    await resolve_rich_text(objs, 'report_comment', 'body', 'plain')
