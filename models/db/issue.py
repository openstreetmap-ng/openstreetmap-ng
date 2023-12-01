from sqlalchemy import Enum, ForeignKey, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.issue_status import IssueStatus
from models.report_type import ReportType
from models.user_role import UserRole


class Issue(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'issue'

    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False)
    report_id: Mapped[str] = mapped_column(Unicode(32), nullable=False)  # max(len(int), len(uuid)) = 32
    assigned_role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)

    # defaults
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus), nullable=False, default=IssueStatus.open)
    updated_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True, default=None)
    updated_user: Mapped[User | None] = relationship(lazy='raise')

    # relationships (nested imports to avoid circular imports)
    from issue_comment import IssueComment
    from report import Report

    issue_comments: Mapped[list[IssueComment]] = relationship(
        back_populates='issue',
        order_by='asc(IssueComment.created_at)',
        lazy='raise',
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates='issue',
        order_by='asc(Report.created_at)',
        lazy='raise',
    )
