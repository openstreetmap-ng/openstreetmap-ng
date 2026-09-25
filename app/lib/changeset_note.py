_MAX_NOTE_ID = (1 << 63) - 1


def parse_note_close_actions(tags: dict[str, str]) -> list[tuple[int, str]]:
    """Parse note ids and closing messages from changeset tags."""
    value = tags.get('closes:note')
    if value is None:
        return []

    default_comment = tags.get('closes:note:comment', tags.get('comment', ''))
    actions: list[tuple[int, str]] = []
    seen: set[int] = set()

    for item in value.split(';'):
        item = item.strip()
        if not item.isdecimal():
            continue

        note_id = int(item)
        if note_id <= 0 or note_id > _MAX_NOTE_ID or note_id in seen:
            continue
        seen.add(note_id)

        comment_key = f'closes:note:{note_id}:comment'
        comment = tags.get(comment_key, default_comment)
        actions.append((note_id, comment))

    actions.sort(key=lambda action: action[0])
    return actions
