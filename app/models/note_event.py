from enum import Enum


class NoteEvent(str, Enum):
    opened = 'opened'
    closed = 'closed'
    reopened = 'reopened'
    commented = 'commented'
    hidden = 'hidden'
