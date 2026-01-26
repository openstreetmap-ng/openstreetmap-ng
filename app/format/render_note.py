import cython
from shapely import get_coordinates

from app.models.db.note import Note, note_status
from app.models.proto.note_pb2 import RenderNotesData
from app.models.proto.shared_pb2 import LonLat


class RenderNoteMixin:
    @staticmethod
    def encode_notes(notes: list[Note]):
        """Format notes into a minimal structure, suitable for map rendering."""
        return RenderNotesData(notes=list(map(_encode_note, notes)))


@cython.cfunc
def _encode_note(note: Note):
    x, y = get_coordinates(note['point'])[0].tolist()
    body = note['comments'][0]['body']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    if len(body) > 100:
        body = body[:100] + '...'
    return RenderNotesData.Note(
        id=note['id'],
        location=LonLat(lon=x, lat=y),
        text=body,
        status=note_status(note),
    )
