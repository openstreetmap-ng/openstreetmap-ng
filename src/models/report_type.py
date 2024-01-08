from typing import Self

from src.models.base_enum import BaseEnum
from src.models.report_category import ReportCategory
from src.models.user_role import UserRole


class ReportType(BaseEnum):
    diary = 'diary'
    diary_comment = 'diary_comment'
    note = 'note'
    user = 'user'

    @staticmethod
    def get_user_role(report_type: Self, category: ReportCategory) -> UserRole:
        # TODO: why admins handle so many reports?
        if report_type == ReportType.note:
            return UserRole.moderator
        if report_type == ReportType.user and category == ReportCategory.vandal:
            return UserRole.moderator
        return UserRole.administrator
