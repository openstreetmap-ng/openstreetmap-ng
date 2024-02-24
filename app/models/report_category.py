from enum import Enum


class ReportCategory(str, Enum):
    spam = 'spam'
    offensive = 'offensive'
    threat = 'threat'
    vandal = 'vandal'
    personal = 'personal'
    abusive = 'abusive'
    other = 'other'
