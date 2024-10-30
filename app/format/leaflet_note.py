from collections.abc import Iterable

import cython
import numpy as np
from shapely import lib

from app.models.db.note import Note
from app.models.leaflet import NoteLeaflet


class LeafletNoteMixin:
    @staticmethod
    def encode_notes(notes: Iterable[Note]) -> tuple[NoteLeaflet, ...]:
        """
        Format notes into a minimal structure, suitable for Leaflet rendering.
        """
        return tuple(_encode_note(note) for note in notes)


@cython.cfunc
def _encode_note(note: Note):
    return NoteLeaflet(
        id=note.id,
        geom=lib.get_coordinates(np.asarray(note.point, dtype=object), False, False)[0][::-1].tolist(),
        text=note.comments[0].body[:100],
        open=note.closed_at is None,
    )
