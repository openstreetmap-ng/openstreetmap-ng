from models.base_enum import BaseEnum


class NoteEvent(BaseEnum):
    opened = 'opened'
    closed = 'closed'
    reopened = 'reopened'
    commented = 'commented'
