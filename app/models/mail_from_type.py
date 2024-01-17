from app.models.base_enum import BaseEnum


class MailFromType(BaseEnum):
    system = 'system'
    message = 'message'
    diary_comment = 'diary_comment'
