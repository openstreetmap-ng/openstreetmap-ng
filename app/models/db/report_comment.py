from datetime import datetime
from typing import NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.db.diary import Diary
from app.models.db.message import Message
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.trace import Trace
from app.models.db.user import UserDisplay
from app.models.proto.admin_users_types import Role
from app.models.proto.report_types import CreateRequest_Action, CreateRequest_Category
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

type ReportActionId = (
    ChangesetId | DiaryId | MessageId | NoteId | ApplicationId | UserId | TraceId | None
)


class ReportCommentInit(TypedDict):
    id: ReportCommentId
    report_id: ReportId
    user_id: UserId
    action: CreateRequest_Action
    action_id: ReportActionId
    body: str  # TODO: validate size
    category: CreateRequest_Category | None
    visible_to: Role


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
