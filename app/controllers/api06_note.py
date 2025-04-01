from asyncio import TaskGroup
from datetime import datetime
from typing import Annotated, Literal

from annotated_types import MinLen
from fastapi import APIRouter, Query, Request
from feedgen.feed import FeedGenerator
from pydantic import BaseModel, PositiveInt

from app.config import (
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_DEFAULT_LIMIT,
    NOTE_QUERY_LEGACY_MAX_LIMIT,
)
from app.format import Format06, FormatRSS06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_rss
from app.lib.geo_utils import parse_bbox
from app.lib.translation import t
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment, note_comments_resolve_rich_text
from app.models.db.user import User
from app.models.types import DisplayName, Latitude, Longitude, NoteId, UserId
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.user_query import UserQuery
from app.responses.osm_response import GPXResponse
from app.services.note_service import NoteService
from app.validators.date import DateValidator

router = APIRouter(prefix='/api/0.6')

# TODO: validate input lengths


@router.post('/notes')
@router.post('/notes.xml')
@router.post('/notes.gpx', response_class=GPXResponse)
async def create_note1(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    text: Annotated[str, Query(min_length=1)],
):
    note_id = await NoteService.create(lon, lat, text)
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    await _resolve_comments_full(notes)
    return Format06.encode_note(notes[0])


class _CreateNote(BaseModel):
    lon: Longitude
    lat: Latitude
    text: Annotated[str, MinLen(1)]


@router.post('/notes.json')
async def create_note2(body: _CreateNote):
    note_id = await NoteService.create(body.lon, body.lat, body.text)
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    await _resolve_comments_full(notes)
    return Format06.encode_note(notes[0])


@router.post('/notes/{note_id:int}/comment')
@router.post('/notes/{note_id:int}/comment.xml')
@router.post('/notes/{note_id:int}/comment.json')
@router.post('/notes/{note_id:int}/comment.gpx', response_class=GPXResponse)
async def create_note_comment(
    note_id: NoteId,
    text: Annotated[str, Query(min_length=1)],
    _: Annotated[User, api_user('write_notes')],
):
    await NoteService.comment(note_id, text, 'commented')
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    await _resolve_comments_full(notes)
    return Format06.encode_note(notes[0])


@router.get('/notes/{note_id:int}')
@router.get('/notes/{note_id:int}.xml')
@router.get('/notes/{note_id:int}.json')
@router.get('/notes/{note_id:int}.rss')
@router.get('/notes/{note_id:int}.gpx', response_class=GPXResponse)
async def get_note(
    request: Request,
    note_id: NoteId,
):
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    if not notes:
        raise_for.note_not_found(note_id)

    await _resolve_comments_full(notes)

    # Alternate path for making RSS response
    if format_is_rss():
        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))
        fg.subtitle(t('api.notes.rss.description_item').format(id=note_id))
        await FormatRSS06.encode_notes(fg, notes)
        return fg.rss_str()

    return Format06.encode_note(notes[0])


@router.post('/notes/{note_id:int}/close')
@router.post('/notes/{note_id:int}/close.xml')
@router.post('/notes/{note_id:int}/close.json')
@router.post('/notes/{note_id:int}/close.gpx', response_class=GPXResponse)
async def close_note(
    _: Annotated[User, api_user('write_notes')],
    note_id: NoteId,
    text: Annotated[str, Query()] = '',
):
    await NoteService.comment(note_id, text, 'closed')
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    await _resolve_comments_full(notes)
    return Format06.encode_note(notes[0])


@router.post('/notes/{note_id:int}/reopen')
@router.post('/notes/{note_id:int}/reopen.xml')
@router.post('/notes/{note_id:int}/reopen.json')
@router.post('/notes/{note_id:int}/reopen.gpx', response_class=GPXResponse)
async def reopen_note(
    _: Annotated[User, api_user('write_notes')],
    note_id: NoteId,
    text: Annotated[str, Query()] = '',
):
    await NoteService.comment(note_id, text, 'reopened')
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    await _resolve_comments_full(notes)
    return Format06.encode_note(notes[0])


@router.delete('/notes/{note_id:int}')
@router.delete('/notes/{note_id:int}.xml')
@router.delete('/notes/{note_id:int}.json')
@router.delete('/notes/{note_id:int}.gpx', response_class=GPXResponse)
async def hide_note(
    _: Annotated[User, api_user('write_notes', 'role_moderator')],
    note_id: NoteId,
    text: Annotated[str, Query()] = '',
):
    await NoteService.comment(note_id, text, 'hidden')
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    await _resolve_comments_full(notes)
    return Format06.encode_note(notes[0])


@router.get('/notes/feed')
@router.get('/notes/feed.rss')
async def get_feed(
    request: Request,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
):
    if bbox is not None:
        geometry = parse_bbox(bbox)
        if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
            raise_for.notes_query_area_too_big()
    else:
        geometry = None

    comments = await NoteCommentQuery.legacy_find_many_by_query(
        geometry=geometry,
        limit=NOTE_QUERY_DEFAULT_LIMIT,
    )

    async with TaskGroup() as tg:
        tg.create_task(_resolve_comments_full(comments))
        tg.create_task(NoteQuery.resolve_legacy_note(comments))

    fg = FeedGenerator()
    fg.link(href=str(request.url), rel='self')
    fg.title(t('api.notes.rss.title'))

    if geometry is not None:
        minx, miny, maxx, maxy = geometry.bounds
        fg.subtitle(
            t('api.notes.rss.description_area').format(
                min_lon=minx,
                min_lat=miny,
                max_lon=maxx,
                max_lat=maxy,
            )
        )
    else:
        fg.subtitle(t('api.notes.rss.description_all'))

    await FormatRSS06.encode_note_comments(fg, comments)
    return fg.rss_str()


@router.get('/notes')
@router.get('/notes.xml')
@router.get('/notes.json')
@router.get('/notes.rss')
@router.get('/notes.gpx', response_class=GPXResponse)
async def query_notes1(
    request: Request,
    bbox: Annotated[str, Query()],
    closed: Annotated[float, Query()] = NOTE_QUERY_DEFAULT_CLOSED,
    limit: Annotated[PositiveInt, Query(le=NOTE_QUERY_LEGACY_MAX_LIMIT)] = NOTE_QUERY_DEFAULT_LIMIT,
):
    geometry = parse_bbox(bbox)
    if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
        raise_for.notes_query_area_too_big()

    notes = await NoteQuery.find_many_by_query(
        geometry=geometry,
        max_closed_days=closed if closed >= 0 else None,
        limit=limit,
    )
    await _resolve_comments_full(notes)

    # Alternate path for making RSS response
    if format_is_rss():
        minx, miny, maxx, maxy = geometry.bounds
        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))
        fg.subtitle(
            t('api.notes.rss.description_area').format(
                min_lon=minx,
                min_lat=miny,
                max_lon=maxx,
                max_lat=maxy,
            )
        )
        await FormatRSS06.encode_notes(fg, notes)
        return fg.rss_str()

    return Format06.encode_notes(notes)


@router.get('/notes/search')
@router.get('/notes/search.xml')
@router.get('/notes/search.json')
@router.get('/notes/search.rss')
@router.get('/notes/search.gpx', response_class=GPXResponse)
async def query_notes2(
    request: Request,
    q: Annotated[str | None, Query()] = None,
    closed: Annotated[float, Query()] = NOTE_QUERY_DEFAULT_CLOSED,
    display_name: Annotated[DisplayName | None, Query(min_length=1)] = None,
    user_id: Annotated[UserId | None, Query(alias='user')] = None,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    from_: Annotated[datetime | None, DateValidator, Query(alias='from')] = None,
    to: Annotated[datetime | None, DateValidator, Query()] = None,
    sort: Annotated[Literal['created_at', 'updated_at'], Query()] = 'updated_at',
    order: Annotated[Literal['oldest', 'newest'], Query()] = 'newest',
    limit: Annotated[PositiveInt, Query(le=NOTE_QUERY_LEGACY_MAX_LIMIT)] = NOTE_QUERY_DEFAULT_LIMIT,
):
    # Logical optimizations
    if (
        ((from_ is not None) and (to is not None) and (from_ >= to))  # Invalid date range
        or ((q is not None) and (not q.strip()))  # Empty query text
    ):
        return Format06.encode_notes([])

    if display_name is not None:
        user = await UserQuery.find_one_by_display_name(display_name)
        if user is None:
            raise_for.user_not_found_bad_request(display_name)
    elif user_id is not None:
        user = await UserQuery.find_one_by_id(user_id)
        if user is None:
            raise_for.user_not_found_bad_request(user_id)
    else:
        user = None

    if bbox is not None:
        geometry = parse_bbox(bbox)
        if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
            raise_for.notes_query_area_too_big()
    else:
        geometry = None

    notes = await NoteQuery.find_many_by_query(
        phrase=q,
        user_id=user['id'] if (user is not None) else None,
        max_closed_days=closed if closed >= 0 else None,
        geometry=geometry,
        date_from=from_,
        date_to=to,
        sort_by='created_at' if sort == 'created_at' else 'updated_at',
        sort_dir='asc' if order == 'oldest' else 'desc',
        limit=limit,
    )
    await _resolve_comments_full(notes)

    # Alternate path for making RSS response
    if format_is_rss():
        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))

        if geometry is not None:
            minx, miny, maxx, maxy = geometry.bounds
            fg.subtitle(
                t('api.notes.rss.description_area').format(
                    min_lon=minx,
                    min_lat=miny,
                    max_lon=maxx,
                    max_lat=maxy,
                )
            )
        else:
            fg.subtitle(t('api.notes.rss.description_all'))
        await FormatRSS06.encode_notes(fg, notes)
        return fg.rss_str()

    return Format06.encode_notes(notes)


async def _resolve_comments_full(notes_or_comments: list[Note] | list[NoteComment]) -> None:
    """Resolve note comments, their rich text and users."""
    if not notes_or_comments:
        return

    if 'body' not in notes_or_comments[0]:
        notes: list[Note] = notes_or_comments  # type: ignore
        comments = await NoteCommentQuery.resolve_comments(notes, per_note_limit=None)
    else:
        comments: list[NoteComment] = notes_or_comments  # type: ignore

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))  # TODO: user is optional
        tg.create_task(note_comments_resolve_rich_text(comments))
