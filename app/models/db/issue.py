import enum

from sqlalchemy import Enum, ForeignKey, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User, UserRole


class ReportType(str, enum.Enum):
    diary = 'diary'
    diary_comment = 'diary_comment'
    note = 'note'
    user = 'user'

    # TODO: in service
    # @staticmethod
    # def get_user_role(report_type: 'ReportType', category: ReportCategory) -> UserRole:
    #     # TODO: why admins handle so many reports?
    #     if report_type == ReportType.note:
    #         return UserRole.moderator
    #     if report_type == ReportType.user and category == ReportCategory.vandal:
    #         return UserRole.moderator
    #     return UserRole.administrator


class IssueStatus(str, enum.Enum):
    open = 'open'
    resolved = 'resolved'
    ignored = 'ignored'


class Issue(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'issue'

    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False)
    report_id: Mapped[str] = mapped_column(Unicode(32), nullable=False)
    assigned_role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)

    # defaults
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus), nullable=False, server_default='open')
    updated_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True, server_default=None)
    updated_user: Mapped[User | None] = relationship(lazy='raise')
