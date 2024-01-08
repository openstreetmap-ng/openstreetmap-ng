from sqlalchemy import Enum, ForeignKey, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.created_at_mixin import CreatedAtMixin
from src.models.db.updated_at_mixin import UpdatedAtMixin
from src.models.db.user import User
from src.models.issue_status import IssueStatus
from src.models.report_type import ReportType
from src.models.user_role import UserRole


class Issue(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'issue'

    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False)
    report_id: Mapped[str] = mapped_column(Unicode(32), nullable=False)  # max(len(int), len(uuid)) == 32
    assigned_role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)

    # defaults
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus), nullable=False, default=IssueStatus.open)
    updated_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True, default=None)
    updated_user: Mapped[User | None] = relationship(lazy='raise')
