from collections.abc import Sequence

import numpy as np
from shapely import lib

from app.models.db.note import Note
from app.models.msgspec.leaflet import NoteLeaflet


class LeafletNoteMixin:
    @staticmethod
    def encode_notes(notes: Sequence[Note]) -> Sequence[NoteLeaflet]:
        """
        Format notes into a minimal structure, suitable for Leaflet rendering.
        """
        return tuple(
            NoteLeaflet(
                type='note',
                id=note.id,
                geom=lib.get_coordinates(np.asarray(note.point, dtype=object), False, False)[0][::-1].tolist(),
                text=note.comments[0].body[:100],
                open=note.closed_at is None,
            )
            for note in notes
        )
