from asyncio import TaskGroup
from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, Form, Query, Response
from psycopg.sql import SQL
from shapely import get_coordinates

from app.config import (
    NOTE_COMMENT_BODY_MAX_LENGTH,
    NOTE_COMMENTS_PAGE_SIZE,
    NOTE_FRESHLY_CLOSED_TIMEOUT,
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_WEB_LIMIT,
    NOTE_USER_PAGE_SIZE,
)
from app.format import FormatRender
from app.lib.auth_context import web_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response,
    sp_render_response_bytes,
)
from app.models.db.note import Note, note_status
from app.models.db.note_comment import (
    NoteComment,
    NoteEvent,
    note_comments_resolve_rich_text,
)
from app.models.db.user import User, user_proto
from app.models.proto.note_pb2 import NoteCommentPage, NoteCommentResult, NoteData
from app.models.proto.shared_pb2 import LonLat
from app.models.types import Latitude, Longitude, NoteId, UserId
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.note_service import NoteService
from app.utils import id_response

router = APIRouter(prefix='/api/web/note')


@router.post('')
async def create_note(
    lon: Annotated[Longitude, Form()],
    lat: Annotated[Latitude, Form()],
    text: Annotated[str, Form(min_length=1, max_length=NOTE_COMMENT_BODY_MAX_LENGTH)],
):
    note_id = await NoteService.create(lon, lat, text)
    return id_response(note_id)


@router.post('/{note_id:int}/comment')
async def create_note_comment(
    _: Annotated[User, web_user()],
    note_id: NoteId,
    event: Annotated[NoteEvent, Form()],
    text: Annotated[str, Form(max_length=NOTE_COMMENT_BODY_MAX_LENGTH)] = '',
):
    await NoteService.comment(note_id, text, event)

    async with TaskGroup() as tg:
        note_t = tg.create_task(build_note_data(note_id))
        comments_t = tg.create_task(build_note_comments_page(note_id))

    comments_page, state = comments_t.result()
    result = NoteCommentResult(note=note_t.result(), comments=comments_page)
    return sp_render_response_bytes(result.SerializeToString(), state)


@router.get('/map')
async def get_map(bbox: Annotated[str, Query()]):
    geometry = parse_bbox(bbox)
    if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
        raise_for.notes_query_area_too_big()

    notes = await NoteQuery.find(
        geometry=geometry,
        max_closed_days=NOTE_QUERY_DEFAULT_CLOSED,
        sort_by='updated_at',
        sort_dir='desc',
        limit=NOTE_QUERY_WEB_LIMIT,
    )

    await NoteCommentQuery.resolve_comments(
        notes, per_note_sort='asc', per_note_limit=1
    )

    return Response(
        FormatRender.encode_notes(notes).SerializeToString(),
        media_type='application/x-protobuf',
    )


@router.post('/{note_id:int}/comments')
async def comments_page(
    note_id: NoteId,
    sp_state: StandardPaginationStateBody = b'',
):
    notes = await NoteQuery.find(note_ids=[note_id], limit=1)
    if not notes:
        raise_for.note_not_found(note_id)

    page, state = await build_note_comments_page(note_id, sp_state)
    return sp_render_response_bytes(page.SerializeToString(), state)


@router.post('/user/{user_id:int}')
async def user_notes_page(
    user_id: UserId,
    commented: Annotated[bool, Query()],
    status: Annotated[Literal['', 'open', 'closed'], Query()],
    sp_state: StandardPaginationStateBody = b'',
):
    open = status == 'open' if status else None

    where_clause, params = NoteQuery.user_page_where(
        user_id,
        commented_other=commented,
        open=open,
    )
    notes, state = await sp_paginate_table(
        Note,
        sp_state,
        table='note',
        where=where_clause,
        params=params,
        page_size=NOTE_USER_PAGE_SIZE,
        cursor_column='updated_at',
        cursor_kind='datetime',
        order_dir='desc',
    )

    async with TaskGroup() as tg:
        tg.create_task(NoteCommentQuery.resolve_num_comments(notes))
        comments = await NoteCommentQuery.resolve_comments(
            notes, per_note_sort='asc', per_note_limit=1
        )
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(note_comments_resolve_rich_text(comments))

    return await sp_render_response(
        'notes/user-page',
        {'notes': notes},
        state,
    )


async def build_note_data(note_id: NoteId):
    notes = await NoteQuery.find(note_ids=[note_id], limit=1)
    note = next(iter(notes), None)
    if note is None:
        raise_for.note_not_found(note_id)

    async with TaskGroup() as tg:
        is_subscribed_t = tg.create_task(
            UserSubscriptionQuery.is_subscribed('note', note_id)
        )
        comments = await NoteCommentQuery.resolve_comments(
            notes, per_note_sort='asc', per_note_limit=1
        )
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(note_comments_resolve_rich_text(comments))

    header = comments[0]
    header_user = header.get('user')
    x, y = get_coordinates(note['point'])[0].tolist()
    status = note_status(note)

    closed_at = note['closed_at']
    if closed_at is not None:
        duration = closed_at + NOTE_FRESHLY_CLOSED_TIMEOUT - utcnow()
        duration_sec = duration.total_seconds()
        disappear_days = ceil(duration_sec / 86400) if (duration_sec > 0) else None
    else:
        disappear_days = None

    return NoteData(
        id=note_id,
        location=LonLat(lon=x, lat=y),
        status=status,
        header=NoteData.Header(
            user=user_proto(header_user),
            created_at=int(header['created_at'].timestamp()),
            body_rich=header['body_rich'] if header['body'] else '',  # type: ignore
        ),
        is_subscribed=is_subscribed_t.result(),
        disappear_days=disappear_days,
    )


async def build_note_comments_page(note_id: NoteId, sp_state: bytes = b''):
    comments, state = await sp_paginate_table(
        NoteComment,
        sp_state,
        table='note_comment',
        where=SQL("note_id = %s AND event != 'opened'"),
        params=(note_id,),
        page_size=NOTE_COMMENTS_PAGE_SIZE,
        order_dir='desc',
        display_dir='asc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(note_comments_resolve_rich_text(comments))

    page = NoteCommentPage(
        comments=[
            NoteCommentPage.Comment(
                user=user_proto(c.get('user')),
                event=c['event'],
                created_at=int(c['created_at'].timestamp()),
                body_rich=c.get('body_rich', ''),
            )
            for c in comments
        ]
    )
    return page, state
