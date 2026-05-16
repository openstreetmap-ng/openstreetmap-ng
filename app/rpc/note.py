from asyncio import TaskGroup
from math import ceil
from typing import assert_never, override

from connectrpc.request import RequestContext
from shapely import get_coordinates

from app.config import (
    NOTE_COMMENTS_PAGE_SIZE,
    NOTE_FRESHLY_CLOSED_TIMEOUT,
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_WEB_LIMIT,
    NOTE_USER_PAGE_SIZE,
)
from app.exceptions.context import raise_for
from app.format import FormatRender
from app.lib.auth.context import require_web_user
from app.lib.geo.parse import parse_bbox
from app.lib.standard.pagination import (
    StandardPaginationRequestLike,
    sp_paginate_table,
)
from app.lib.time.date_utils import utcnow
from app.models.db.note import Note, note_status
from app.models.db.note_comment import NoteComment, note_comments_resolve_rich_text
from app.models.db.user import user_proto
from app.models.proto.note_connect import Service as NoteServiceConnect
from app.models.proto.note_connect import ServiceASGIApplication
from app.models.proto.note_pb2 import (
    AddCommentRequest,
    AddCommentResponse,
    CreateRequest,
    CreateResponse,
    Data,
    GetCommentsRequest,
    GetCommentsResponse,
    GetMapRequest,
    GetRequest,
    GetResponse,
    GetUserPageRequest,
    GetUserPageResponse,
)
from app.models.proto.shared_pb2 import LonLat
from app.models.types import NoteId, UserId
from app.queries.note_query import NoteCommentQuery, NoteQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.note_service import NoteService


class _Service(NoteServiceConnect):
    @override
    async def get_map(self, request: GetMapRequest, ctx: RequestContext):
        geometry = parse_bbox(request.bbox)
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

        return FormatRender.encode_notes(notes)

    @override
    async def get(self, request: GetRequest, ctx: RequestContext):
        id = NoteId(request.id)
        return GetResponse(note=await _build_data(id))

    @override
    async def get_comments(self, request: GetCommentsRequest, ctx: RequestContext):
        id = NoteId(request.id)
        if not await NoteQuery.find(note_ids=[id], limit=1):
            raise_for.note_not_found(id)

        return await _build_comments(id, request.state)

    @override
    async def get_user_page(self, request: GetUserPageRequest, ctx: RequestContext):
        user_id = UserId(request.user_id)
        if await UserQuery.find_by_id(user_id) is None:
            raise_for.user_not_found(user_id)

        open: bool | None
        if request.status == GetUserPageRequest.StatusFilter.open:
            open = True
        elif request.status == GetUserPageRequest.StatusFilter.closed:
            open = False
        elif request.status == GetUserPageRequest.StatusFilter.any:
            open = None
        else:
            assert_never(request.status)

        where = NoteQuery.user_page_where(
            user_id,
            commented_other=request.commented,
            open=open,
        )

        notes, state = await sp_paginate_table(
            Note,
            request.state,
            table='note',
            where=where,
            page_size=NOTE_USER_PAGE_SIZE,
            cursor_column='updated_at',
            cursor_kind='datetime',
            order_dir='desc',
        )

        comments = await NoteCommentQuery.resolve_comments(
            notes, per_note_sort='asc', per_note_limit=1
        )

        async with TaskGroup() as tg:
            tg.create_task(NoteCommentQuery.resolve_num_comments(notes))
            tg.create_task(UserQuery.resolve_users(comments))

        response = GetUserPageResponse()
        response.state.CopyFrom(state)
        for note in notes:
            header = note['comments'][0]  # type: ignore[reportTypedDictNotRequiredAccess]
            summary = response.notes.add()
            summary.id = note['id']
            summary.status = note_status(note)
            summary.created_at = int(header['created_at'].timestamp())
            if (created_by := user_proto(header.get('user'))) is not None:
                summary.created_by.CopyFrom(created_by)
            summary.body = header.get('body') or ''
            summary.updated_at = int(note['updated_at'].timestamp())
            summary.num_comments = note.get('num_comments') or 0

        return response

    @override
    async def create(self, request: CreateRequest, ctx: RequestContext):
        note_id = await NoteService.create(
            request.location.lon, request.location.lat, request.body
        )
        return CreateResponse(id=note_id)

    @override
    async def add_comment(self, request: AddCommentRequest, ctx: RequestContext):
        require_web_user()

        id = NoteId(request.id)
        event = GetCommentsResponse.Comment.Event.Name(request.event)
        await NoteService.comment(id, request.body, event)

        async with TaskGroup() as tg:
            note_t = tg.create_task(_build_data(id))
            comments_t = tg.create_task(_build_comments(id))

        return AddCommentResponse(note=note_t.result(), comments=comments_t.result())


service = _Service()
asgi_app_cls = ServiceASGIApplication


async def _build_data(note_id: NoteId):
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

    return Data(
        id=note_id,
        location=LonLat(lon=x, lat=y),
        status=status,
        header=Data.Header(
            user=user_proto(header_user),
            created_at=int(header['created_at'].timestamp()),
            body_rich=header['body_rich'] if header['body'] else '',  # type: ignore
        ),
        is_subscribed=is_subscribed_t.result(),
        disappear_days=disappear_days,
    )


async def _build_comments(
    note_id: NoteId, sp_state: StandardPaginationRequestLike = b''
):
    comments, state = await sp_paginate_table(
        NoteComment,
        sp_state,
        table='note_comment',
        where=t"note_id = {note_id} AND event != 'opened'",
        page_size=NOTE_COMMENTS_PAGE_SIZE,
        order_dir='desc',
        display_dir='asc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(note_comments_resolve_rich_text(comments))

    page = GetCommentsResponse()
    page.state.CopyFrom(state)
    for c in comments:
        comment = page.comments.add()
        if (user := user_proto(c.get('user'))) is not None:
            comment.user.CopyFrom(user)
        comment.event = c['event']
        comment.created_at = int(c['created_at'].timestamp())
        comment.body_rich = c.get('body_rich', '')
    return page
