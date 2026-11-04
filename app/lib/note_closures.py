from app.models.types import NoteId


def note_closures(tags: dict[str, str]) -> dict[NoteId, str]:
    """Parse positive bigint note IDs and their explicit comment overrides."""
    result: dict[NoteId, str] = {}
    default = tags.get('closes:note:comment', tags.get('comment', ''))
    for value in tags.get('closes:note', '').split(';'):
        value = value.strip()
        if not value.isascii() or not value.isdecimal() or len(value) > 19:
            continue
        note_id = NoteId(int(value))
        if not 0 < note_id <= 9223372036854775807:
            continue
        result[note_id] = tags.get(f'closes:note:{note_id}:comment', default)
    return result
