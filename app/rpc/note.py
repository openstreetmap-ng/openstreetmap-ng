from asyncio import TaskGroup
from math import ceil
from typing import override

from connectrpc.request import RequestContext
from psycopg.sql import SQL
from shapely import get_coordinates

from app.config import (
    NOTE_COMMENTS_PAGE_SIZE,
    NOTE_FRESHLY_CLOSED_TIMEOUT,
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_WEB_LIMIT,
    NOTE_USER_PAGE_SIZE,
)
from app.format import FormatRender
from app.lib.auth_context import require_web_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.standard_pagination import sp_paginate_table
from app.models.db.note import Note, note_status
from app.models.db.note_comment import NoteComment, note_comments_resolve_rich_text
from app.models.db.user import user_proto
from app.models.proto.note_connect import NoteService as NoteServiceConnect
from app.models.proto.note_connect import NoteServiceASGIApplication
from app.models.proto.note_pb2 import (
    AddNoteCommentRequest,
    AddNoteCommentResponse,
    CreateNoteRequest,
    CreateNoteResponse,
    GetMapNotesRequest,
    GetNoteCommentsRequest,
    GetNoteCommentsResponse,
    GetNoteRequest,
    GetNoteResponse,
    GetUserNotesPageRequest,
    GetUserNotesPageResponse,
    NoteData,
    SetNoteSubscriptionRequest,
    SetNoteSubscriptionResponse,
)
from app.models.proto.shared_pb2 import LonLat
from app.models.types import NoteId, UserId
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.note_service import NoteService
from app.services.user_subscription_service import UserSubscriptionService


class _Service(NoteServiceConnect):
    @override
    async def get_map_notes(self, request: GetMapNotesRequest, ctx: RequestContext):
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
    async def get_note(self, request: GetNoteRequest, ctx: RequestContext):
        id = NoteId(request.id)
        return GetNoteResponse(note=await _build_data(id))

    @override
    async def get_note_comments(
        self, request: GetNoteCommentsRequest, ctx: RequestContext
    ):
        id = NoteId(request.id)
        if not await NoteQuery.find(note_ids=[id], limit=1):
            raise_for.note_not_found(id)

        sp_state = request.state.SerializeToString()
        return await _build_comments(id, sp_state)

    @override
    async def get_user_notes_page(
        self, request: GetUserNotesPageRequest, ctx: RequestContext
    ):
        user_id = UserId(request.user_id)
        if await UserQuery.find_by_id(user_id) is None:
            raise_for.user_not_found(user_id)

        open: bool | None
        if request.status == GetUserNotesPageRequest.StatusFilter.open:
            open = True
        elif request.status == GetUserNotesPageRequest.StatusFilter.closed:
            open = False
        else:
            open = None

        where_clause, params = NoteQuery.user_page_where(
            user_id,
            commented_other=request.commented,
            open=open,
        )

        sp_state = request.state.SerializeToString()
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

        comments = await NoteCommentQuery.resolve_comments(
            notes, per_note_sort='asc', per_note_limit=1
        )

        async with TaskGroup() as tg:
            tg.create_task(NoteCommentQuery.resolve_num_comments(notes))
            tg.create_task(UserQuery.resolve_users(comments))

        summaries: list[GetUserNotesPageResponse.Summary] = []
        for note in notes:
            header = note['comments'][0]  # type: ignore[reportTypedDictNotRequiredAccess]
            summaries.append(
                GetUserNotesPageResponse.Summary(
                    id=note['id'],
                    status=note_status(note),
                    created_at=int(header['created_at'].timestamp()),
                    created_by=user_proto(header.get('user')),
                    body=header.get('body') or '',
                    updated_at=int(note['updated_at'].timestamp()),
                    num_comments=note.get('num_comments') or 0,
                )
            )

        return GetUserNotesPageResponse(state=state, notes=summaries)

    @override
    async def create_note(self, request: CreateNoteRequest, ctx: RequestContext):
        note_id = await NoteService.create(
            request.location.lon, request.location.lat, request.body
        )
        return CreateNoteResponse(id=note_id)

    @override
    async def add_note_comment(
        self, request: AddNoteCommentRequest, ctx: RequestContext
    ):
        require_web_user()

        id = NoteId(request.id)
        event = GetNoteCommentsResponse.Comment.Event.Name(request.event)
        await NoteService.comment(id, request.body, event)

        async with TaskGroup() as tg:
            note_t = tg.create_task(_build_data(id))
            comments_t = tg.create_task(_build_comments(id))

        return AddNoteCommentResponse(
            note=note_t.result(), comments=comments_t.result()
        )

    @override
    async def set_note_subscription(
        self, request: SetNoteSubscriptionRequest, ctx: RequestContext
    ):
        require_web_user()

        id = NoteId(request.id)
        if request.is_subscribed:
            await UserSubscriptionService.subscribe('note', id)
        else:
            await UserSubscriptionService.unsubscribe('note', id)

        return SetNoteSubscriptionResponse(is_subscribed=request.is_subscribed)


service = _Service()
asgi_app_cls = NoteServiceASGIApplication


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


async def _build_comments(note_id: NoteId, sp_state: bytes = b''):
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

    page = GetNoteCommentsResponse(
        state=state,
        comments=[
            GetNoteCommentsResponse.Comment(
                user=user_proto(c.get('user')),
                event=c['event'],
                created_at=int(c['created_at'].timestamp()),
                body_rich=c.get('body_rich', ''),
            )
            for c in comments
        ],
    )
    return page
