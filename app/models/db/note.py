from datetime import datetime
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from shapely import Point

from app.models.types import NoteId

if TYPE_CHECKING:
    from app.models.db.note_comment import NoteComment


# TODO: ensure updated at on members
# TODO: pruner

NoteStatus = Literal['open', 'closed', 'hidden']


class NoteInit(TypedDict):
    point: Point


class Note(NoteInit):
    id: NoteId
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    hidden_at: datetime | None

    # runtime
    num_comments: NotRequired[int]
    comments: NotRequired[list['NoteComment']]


def note_status(note: Note) -> NoteStatus:
    """Get the note's status."""
    if note['hidden_at'] is not None:
        return 'hidden'
    if note['closed_at'] is not None:
        return 'closed'
    return 'open'


# TODO: delete forever hidden notes
