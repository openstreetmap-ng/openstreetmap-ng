from enum import Enum


class MailSource(str, Enum):
    system = 'system'
    message = 'message'
    diary_comment = 'diary_comment'
