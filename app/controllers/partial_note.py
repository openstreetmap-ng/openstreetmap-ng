from collections.abc import Iterable
from math import ceil

from anyio import create_task_group
from fastapi import APIRouter
from pydantic import PositiveInt
from shapely import get_coordinates
from sqlalchemy.orm import joinedload

from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import NOTE_FRESHLY_CLOSED_TIMEOUT
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.db.user import User
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/api/partial/note')


@router.get('/{id:int}')
async def get_note(id: PositiveInt):
    notes = await NoteQuery.find_many_by_query(note_ids=(id,), limit=1)
    note = notes[0] if notes else None
    if note is None:
        return render_response(
            'partial/not_found.jinja2',
            {'type': 'note', 'id': id},
        )

    is_subscribed = False

    async def resolve_comments_task():
        await _resolve_comments_full(notes)

    async def subscription_task():
        nonlocal is_subscribed
        is_subscribed = await NoteCommentQuery.is_subscribed(id)

    async with create_task_group() as tg:
        tg.start_soon(resolve_comments_task)
        if auth_user() is not None:
            tg.start_soon(subscription_task)

    # TODO: pagination

    disappear_days: int | None = None
    if note.closed_at is not None:
        duration = note.closed_at + NOTE_FRESHLY_CLOSED_TIMEOUT - utcnow()
        disappear_days = ceil(duration.total_seconds() / 86400)
        if duration.total_seconds() <= 0:
            disappear_days = None

    x, y = get_coordinates(note.point)[0].tolist()
    return render_response(
        'partial/note.jinja2',
        {
            'note': note,
            'header': note.comments[0],
            'comments': note.comments[1:],
            'status': note.status.value,
            'is_subscribed': is_subscribed,
            'disappear_days': disappear_days,
            'params': JSON_ENCODE(
                {
                    'id': id,
                    'lon': x,
                    'lat': y,
                    'open': note.closed_at is None,
                }
            ).decode(),
        },
    )


async def _resolve_comments_full(notes: Iterable[Note]) -> None:
    """
    Resolve note comments, their rich text and users.
    """
    with options_context(
        joinedload(NoteComment.user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        comments = await NoteCommentQuery.resolve_comments(notes, per_note_limit=None)

    async with create_task_group() as tg:
        for comment in comments:
            tg.start_soon(comment.resolve_rich_text)
