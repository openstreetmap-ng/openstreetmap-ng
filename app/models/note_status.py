from enum import Enum


class NoteStatus(str, Enum):
    open = 'open'
    closed = 'closed'
    hidden = 'hidden'
