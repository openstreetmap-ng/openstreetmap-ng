from asyncio import TaskGroup
from base64 import urlsafe_b64encode
from math import ceil

from fastapi import APIRouter
from shapely import get_coordinates
from starlette import status

from app.lib.date_utils import utcnow
from app.lib.render_response import render_response
from app.limits import NOTE_COMMENTS_PAGE_SIZE, NOTE_FRESHLY_CLOSED_TIMEOUT
from app.models.db.note import note_status
from app.models.db.note_comment import note_comments_resolve_rich_text
from app.models.proto.shared_pb2 import PartialNoteParams
from app.models.types import NoteId
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery

router = APIRouter(prefix='/partial/note')


# TODO: pagination discussion, note, changeset, diary
@router.get('/{id:int}')
async def get_note(id: NoteId):
    notes = await NoteQuery.find_many_by_query(note_ids=[id], limit=1)
    note = next(iter(notes), None)
    if note is None:
        return await render_response(
            'partial/not_found.jinja2',
            {'type': 'note', 'id': id},
            status=status.HTTP_404_NOT_FOUND,
        )

    async with TaskGroup() as tg:
        is_subscribed_t = tg.create_task(UserSubscriptionQuery.is_subscribed('note', id))
        comments = await NoteCommentQuery.resolve_comments(notes, per_note_sort='asc', per_note_limit=1)
        tg.create_task(NoteCommentQuery.resolve_num_comments(notes))
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(note_comments_resolve_rich_text(comments))

    closed_at = note['closed_at']
    if closed_at is not None:
        duration = closed_at + NOTE_FRESHLY_CLOSED_TIMEOUT - utcnow()
        duration_sec = duration.total_seconds()
        disappear_days = ceil(duration_sec / 86400) if (duration_sec > 0) else None
    else:
        disappear_days = None

    note_comments_num_items = note['num_comments'] - 1  # pyright: ignore [reportTypedDictNotRequiredAccess]
    note_comments_num_pages = ceil(note_comments_num_items / NOTE_COMMENTS_PAGE_SIZE)

    x, y = get_coordinates(note['point'])[0].tolist()
    place = f'{y:.5f}, {x:.5f}'
    params = PartialNoteParams(id=id, lon=x, lat=y, status=note_status(note))

    return await render_response(
        'partial/note.jinja2',
        {
            'note': note,
            'place': place,
            'header': comments[0],
            'note_comments_num_items': note_comments_num_items,
            'note_comments_num_pages': note_comments_num_pages,
            'status': note_status(note),
            'is_subscribed': is_subscribed_t.result(),
            'disappear_days': disappear_days,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
        },
    )
