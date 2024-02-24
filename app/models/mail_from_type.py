from enum import Enum


class MailFromType(str, Enum):
    system = 'system'
    message = 'message'
    diary_comment = 'diary_comment'
