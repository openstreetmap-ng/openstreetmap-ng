from app.models.base_enum import BaseEnum


class IssueStatus(BaseEnum):
    open = 'open'
    resolved = 'resolved'
    ignored = 'ignored'
