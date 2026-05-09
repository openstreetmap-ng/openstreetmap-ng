from collections.abc import Mapping


def changeset_note_closures(tags: Mapping[str, str]) -> list[tuple[int, str]]:
    note_ids_tag = tags.get('closes:note')
    if not note_ids_tag:
        return []

    default_comment = tags.get('closes:note:comment', tags.get('comment', ''))
    closures: list[tuple[int, str]] = []
    seen: set[int] = set()

    for note_id_str in note_ids_tag.split(';'):
        note_id_str = note_id_str.strip()
        if not note_id_str.isdecimal():
            continue

        note_id = int(note_id_str)
        if note_id <= 0 or note_id in seen:
            continue

        seen.add(note_id)
        comment = tags.get(f'closes:note:{note_id}:comment', default_comment)
        closures.append((note_id, comment))

    return closures
