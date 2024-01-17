from app.models.base_enum import BaseEnum


class ReportCategory(BaseEnum):
    spam = 'spam'
    offensive = 'offensive'
    threat = 'threat'
    vandal = 'vandal'
    personal = 'personal'
    abusive = 'abusive'
    other = 'other'
