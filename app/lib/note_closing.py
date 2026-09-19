from app.models.types import NoteId


def parse_note_closures(tags: dict[str, str]):
    """Resolve unique note IDs and comments from changeset closure tags."""
    ids: set[NoteId] = set()
    for value in tags.get('closes:note', '').split(';'):
        value = value.strip()
        if not value or not value.isascii() or not value.isdecimal():
            continue
        # PostgreSQL note IDs are positive signed bigint values.
        value = value.lstrip('0')
        if not value or len(value) > 19:
            continue
        note_id = NoteId(int(value))
        if note_id <= 9223372036854775807:
            ids.add(note_id)

    default = tags.get('closes:note:comment', tags.get('comment', ''))
    # Stable lock order also removes duplicate close events within one changeset.
    return [
        (note_id, tags.get(f'closes:note:{note_id}:comment', default))
        for note_id in sorted(ids)
    ]
