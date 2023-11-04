from models.base_enum import BaseEnum


class ReportType(BaseEnum):
    diary_entry = 'diary_entry'
    diary_entry_comment = 'diary_entry_comment'
    note = 'note'
    user = 'user'
