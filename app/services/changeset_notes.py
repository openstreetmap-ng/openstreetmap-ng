from psycopg import AsyncConnection

from app.db import db_fetchone, db_insert, db_update
from app.lib.audit import audit
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.types import NoteId, UserId
from app.queries.user_query import UserQuery
from app.services.note_service import NoteService


def changeset_note_comments(tags: dict[str, str]) -> dict[NoteId, str]:
    """Resolve valid note IDs and explicit (including empty) comment overrides."""
    default = tags.get('closes:note:comment', tags.get('comment', ''))
    result: dict[NoteId, str] = {}
    for raw in tags.get('closes:note', '').split(';'):
        value = raw.strip()
        if not value.isascii() or not value.isdecimal() or len(value) > 19:
            continue
        id = int(value)
        if 0 < id <= (1 << 63) - 1:
            result[NoteId(id)] = tags.get(f'closes:note:{id}:comment', default)
    return result


async def close_changeset_notes(
    conn: AsyncConnection, user_id: UserId | None, tags: dict[str, str]
) -> list[tuple[Note, NoteComment]]:
    """Mutate notes in the caller's transaction; return post-commit notifications."""
    comments = changeset_note_comments(tags)
    if not comments or user_id is None:
        return []
    user = await UserQuery.find_by_id(user_id)
    if user is None:
        return []

    result = []
    # A stable locking order also handles overlapping note lists safely.
    for note_id, text in sorted(comments.items()):
        note = await db_fetchone(
            Note,
            t"""SELECT * FROM note WHERE id = {note_id}
                AND closed_at IS NULL AND hidden_at IS NULL FOR UPDATE""",
            conn=conn,
        )
        if note is None:
            continue
        comment_id, created_at = await db_insert(
            'note_comment',
            {
                'user_id': user_id,
                'user_ip': None,
                'note_id': note_id,
                'event': 'closed',
                'body': text,
            },
            returning='id, created_at',
            conn=conn,
        )
        await db_update(
            'note',
            {'closed_at': created_at, 'updated_at': created_at},
            where={'id': note_id},
            conn=conn,
        )
        await db_insert(
            'user_subscription',
            {'user_id': user_id, 'target': 'note', 'target_id': note_id},
            on_conflict=t'DO NOTHING',
            conn=conn,
        )
        if text:
            await audit(
                'create_note_comment',
                conn,
                user_id=user_id,
                extra={'id': comment_id, 'note': note_id},
            )
        await audit(
            'update_note_status',
            conn,
            user_id=user_id,
            extra={'id': note_id, 'event': 'closed'},
        )
        comment: NoteComment = {
            'id': comment_id,
            'user_id': user_id,
            'user_ip': None,
            'note_id': note_id,
            'event': 'closed',
            'body': text,
            'body_rich_hash': None,
            'created_at': created_at,
            'user': user,
        }
        result.append((note, comment))
    return result


async def notify_changeset_notes(items: list[tuple[Note, NoteComment]]):
    for note, comment in items:
        await NoteService.notify_activity(note, comment)
