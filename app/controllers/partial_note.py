from asyncio import TaskGroup
from base64 import urlsafe_b64encode
from math import ceil

from fastapi import APIRouter
from pydantic import PositiveInt
from shapely import get_coordinates
from sqlalchemy.orm import joinedload
from starlette import status

from app.lib.date_utils import utcnow
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import NOTE_COMMENTS_PAGE_SIZE, NOTE_FRESHLY_CLOSED_TIMEOUT
from app.models.db.note_comment import NoteComment
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.proto.shared_pb2 import PartialNoteParams
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.user_subscription_query import UserSubscriptionQuery

router = APIRouter(prefix='/api/partial/note')


# TODO: pagination discussion, note, changeset, diary
@router.get('/{id:int}')
async def get_note(id: PositiveInt):
    notes = await NoteQuery.find_many_by_query(note_ids=(id,), limit=1)
    note = notes[0] if notes else None
    if note is None:
        return await render_response(
            'partial/not_found.jinja2',
            {'type': 'note', 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    with options_context(
        joinedload(NoteComment.user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        async with TaskGroup() as tg:
            tg.create_task(NoteCommentQuery.resolve_num_comments(notes))
            tg.create_task(
                NoteCommentQuery.resolve_comments(
                    notes,
                    per_note_sort='asc',
                    per_note_limit=1,
                    resolve_rich_text=True,
                )
            )
            is_subscribed_t = tg.create_task(UserSubscriptionQuery.is_subscribed(UserSubscriptionTarget.note, id))

    if note.closed_at is not None:
        duration = note.closed_at + NOTE_FRESHLY_CLOSED_TIMEOUT - utcnow()
        duration_sec = duration.total_seconds()
        disappear_days = ceil(duration_sec / 86400) if (duration_sec > 0) else None
    else:
        disappear_days = None

    if note.num_comments is None:
        raise AssertionError('Note num comments must be set')
    note_comments_num_items = note.num_comments - 1
    note_comments_num_pages = ceil(note_comments_num_items / NOTE_COMMENTS_PAGE_SIZE)
    x, y = get_coordinates(note.point)[0].tolist()
    place = f'{y:.5f}, {x:.5f}'
    params = PartialNoteParams(id=id, lon=x, lat=y, open=note.closed_at is None)
    return await render_response(
        'partial/note.jinja2',
        {
            'note': note,
            'place': place,
            'header': note.comments[0],
            'note_comments_num_items': note_comments_num_items,
            'note_comments_num_pages': note_comments_num_pages,
            'status': note.status.value,
            'is_subscribed': is_subscribed_t.result(),
            'disappear_days': disappear_days,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
        },
    )
