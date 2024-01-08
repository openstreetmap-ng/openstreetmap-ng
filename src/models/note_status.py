from src.models.base_enum import BaseEnum


class NoteStatus(BaseEnum):
    open = 'open'
    closed = 'closed'
    hidden = 'hidden'
