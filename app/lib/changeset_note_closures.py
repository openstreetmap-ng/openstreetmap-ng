from app.models.types import NoteId


def parse_changeset_note_closures(tags: dict[str, str]) -> dict[NoteId, str]:
    note_ids = _parse_note_ids(tags.get('closes:note'))
    if not note_ids:
        return {}

    default_comment = tags.get('closes:note:comment', tags.get('comment', ''))
    return {
        note_id: tags.get(f'closes:note:{note_id}:comment', default_comment)
        for note_id in note_ids
    }


def _parse_note_ids(value: str | None) -> list[NoteId]:
    if not value:
        return []

    result: list[NoteId] = []
    seen: set[NoteId] = set()
    for raw_note_id in value.split(';'):
        raw_note_id = raw_note_id.strip()
        if not raw_note_id.isdecimal():
            continue

        note_id_int = int(raw_note_id)
        if note_id_int <= 0:
            continue

        note_id = NoteId(note_id_int)
        if note_id in seen:
            continue

        seen.add(note_id)
        result.append(note_id)

    return result
