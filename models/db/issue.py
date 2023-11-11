from datetime import datetime
from typing import Annotated, Any

from pydantic import Field

from models.db.base_sequential import BaseSequential, SequentialId
from models.db.issue_comment import IssueComment
from models.db.report import Report
from models.issue_status import IssueStatus
from models.report_type import ReportType
from models.user_role import UserRole
from utils import utcnow


class Issue(BaseSequential):
    reportable_type: Annotated[ReportType, Field(frozen=True)]
    reportable_id: Annotated[Any, Field(frozen=True)]
    status: IssueStatus
    assigned_role: UserRole

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    updated_at: datetime | None = None
    updated_user_id: SequentialId | None = None

    reports_: Annotated[tuple[Report, ...] | None, Field(exclude=True)] = None
    comments_: Annotated[tuple[IssueComment, ...] | None, Field(exclude=True)] = None
