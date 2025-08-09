from datetime import datetime
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from app.models.db.user import UserDisplay
from app.models.types import NoteId, ReportId, UserId

if TYPE_CHECKING:
    from app.models.db.report_comment import ReportComment

ReportType = Literal['anonymous_note', 'user']
ReportTypeId = NoteId | UserId


class ReportInit(TypedDict):
    id: ReportId
    type: ReportType
    type_id: ReportTypeId


class Report(ReportInit):
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None

    # runtime
    num_comments: NotRequired[int]
    comments: NotRequired[list['ReportComment']]
    reported_user: NotRequired[UserDisplay]
