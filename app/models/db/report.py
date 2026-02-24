from datetime import datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict

from app.models.db.user import UserDisplay
from app.models.proto.report_types import CreateRequest_Type
from app.models.types import NoteId, ReportId, UserId

if TYPE_CHECKING:
    from app.models.db.report_comment import ReportComment

type ReportTypeId = NoteId | UserId


class ReportInit(TypedDict):
    id: ReportId
    type: CreateRequest_Type
    type_id: ReportTypeId


class Report(ReportInit):
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None

    # runtime
    num_comments: NotRequired[int]
    comments: NotRequired[list['ReportComment']]
    reported_user: NotRequired[UserDisplay]
