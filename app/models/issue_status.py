from enum import Enum


class IssueStatus(str, Enum):
    open = 'open'
    resolved = 'resolved'
    ignored = 'ignored'
