from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated

import anyio
from fastapi import APIRouter, Query, Request
from feedgen.feed import FeedGenerator
from pydantic import PositiveInt
from shapely.geometry import Point

from cython_lib.geo_utils import parse_bbox
from lib.auth import api_user
from lib.exceptions import raise_for
from lib.format import format_style
from lib.format.format06 import Format06
from lib.format.format06_rss import Format06RSS
from lib.joinedload_context import joinedload_context
from lib.translation import t
from limits import (
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_DEFAULT_LIMIT,
    NOTE_QUERY_LEGACY_MAX_LIMIT,
)
from models.db.note import Note
from models.db.note_comment import NoteComment
from models.db.user import User
from models.format_style import FormatStyle
from models.geometry import Latitude, Longitude
from models.note_event import NoteEvent
from models.scope import ExtendedScope, Scope
from repositories.note_comment_repository import NoteCommentRepository
from repositories.note_repository import NoteRepository
from repositories.user_repository import UserRepository
from responses.osm_response import GPXResponse
from services.note_service import NoteService
from validators.date import DateValidator

router = APIRouter()

# TODO: validate input lengths


async def _resolve_rich_texts(notes_or_comments: Sequence[Note | NoteComment] | Note | NoteComment) -> None:
    """
    Resolve rich text for notes or comments.
    """

    if not notes_or_comments:
        return

    if isinstance(notes_or_comments, Note | NoteComment):
        notes_or_comments = (notes_or_comments,)

    async with anyio.create_task_group() as tg:
        if isinstance(notes_or_comments[0], NoteComment):
            for comment in notes_or_comments:
                tg.start_soon(comment.resolve_rich_text)
        else:
            for note in notes_or_comments:
                for comment in note.comments:
                    tg.start_soon(comment.resolve_rich_text)


@router.post('/notes')
@router.post('/notes.xml')
@router.post('/notes.json')
@router.post('/notes.gpx', response_class=GPXResponse)
async def note_create(
    request: Request,
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    text: Annotated[str, Query(min_length=1)],
) -> dict:
    point = Point(lon, lat)
    note = await NoteService.create(request, point, text)
    await _resolve_rich_texts(note)
    return Format06.encode_note(note)


@router.get('/notes/{note_id}')
@router.get('/notes/{note_id}.xml')
@router.get('/notes/{note_id}.json')
@router.get('/notes/{note_id}.rss')
@router.get('/notes/{note_id}.gpx', response_class=GPXResponse)
async def note_read(
    request: Request,
    note_id: PositiveInt,
) -> dict:
    with joinedload_context(Note.comments, NoteComment.body_rich):
        notes = await NoteRepository.find_many_by_query(note_ids=[note_id], limit=None)

    if not notes:
        raise_for().note_not_found(note_id)

    await _resolve_rich_texts(notes)

    style = format_style()
    if style == FormatStyle.rss:
        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))
        fg.subtitle(t('api.notes.rss.description_item').format(id=note_id))

        await Format06RSS.encode_notes(fg, notes)
        return fg.rss_str()

    else:
        return Format06.encode_note(notes[0])


@router.post('/notes/{note_id}/comment')
@router.post('/notes/{note_id}/comment.xml')
@router.post('/notes/{note_id}/comment.json')
@router.post('/notes/{note_id}/comment.gpx', response_class=GPXResponse)
async def note_comment(
    note_id: PositiveInt,
    text: Annotated[str, Query(min_length=1)],
    _: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    with joinedload_context(Note.comments, NoteComment.body_rich):
        note = await NoteService.comment(note_id, text, NoteEvent.commented)
    await _resolve_rich_texts(note)
    return Format06.encode_note(note)


@router.post('/notes/{note_id}/close')
@router.post('/notes/{note_id}/close.xml')
@router.post('/notes/{note_id}/close.json')
@router.post('/notes/{note_id}/close.gpx', response_class=GPXResponse)
async def note_close(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    _: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    with joinedload_context(Note.comments, NoteComment.body_rich):
        note = await NoteService.comment(note_id, text, NoteEvent.closed)
    await _resolve_rich_texts(note)
    return Format06.encode_note(note)


@router.post('/notes/{note_id}/reopen')
@router.post('/notes/{note_id}/reopen.xml')
@router.post('/notes/{note_id}/reopen.json')
@router.post('/notes/{note_id}/reopen.gpx', response_class=GPXResponse)
async def note_reopen(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    _: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    with joinedload_context(Note.comments, NoteComment.body_rich):
        note = await NoteService.comment(note_id, text, NoteEvent.reopened)
    await _resolve_rich_texts(note)
    return Format06.encode_note(note)


@router.delete('/notes/{note_id}')
@router.delete('/notes/{note_id}.xml')
@router.delete('/notes/{note_id}.json')
@router.delete('/notes/{note_id}.gpx', response_class=GPXResponse)
async def note_hide(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    _: Annotated[User, api_user(Scope.write_notes, ExtendedScope.role_moderator)],
) -> dict:
    with joinedload_context(Note.comments, NoteComment.body_rich):
        note = await NoteService.comment(note_id, text, NoteEvent.hidden)
    await _resolve_rich_texts(note)
    return Format06.encode_note(note)


@router.get('/notes/feed')
@router.get('/notes/feed.rss')
async def notes_feed(
    request: Request,
    bbox: Annotated[str | None, Query(None, min_length=1)],
) -> Sequence[dict]:
    if bbox:
        geometry = parse_bbox(bbox)

        if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
            raise_for().notes_query_area_too_big()
    else:
        geometry = None

    # TODO: will this work?
    with joinedload_context(NoteComment.body_rich, NoteComment.note, Note.comments):
        comments = await NoteCommentRepository.find_many_by_query(
            geometry=geometry,
            limit=NOTE_QUERY_DEFAULT_LIMIT,
        )

    await _resolve_rich_texts(comments)

    fg = FeedGenerator()
    fg.link(href=str(request.url), rel='self')
    fg.title(t('api.notes.rss.title'))

    if geometry:
        min_lon, min_lat, max_lon, max_lat = geometry.bounds
        fg.subtitle(
            t('api.notes.rss.description_area').format(
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
            )
        )
    else:
        fg.subtitle(t('api.notes.rss.description_all'))

    await Format06RSS.encode_note_comments(fg, comments)
    return fg.rss_str()


@router.get('/notes')
@router.get('/notes.xml')
@router.get('/notes.json')
@router.get('/notes.rss')
@router.get('/notes.gpx', response_class=GPXResponse)
async def notes_read(
    request: Request,
    bbox: Annotated[str, Query(min_length=1)],
    closed: Annotated[int, Query(NOTE_QUERY_DEFAULT_CLOSED)],
    limit: Annotated[PositiveInt, Query(NOTE_QUERY_DEFAULT_LIMIT, le=NOTE_QUERY_LEGACY_MAX_LIMIT)],
) -> Sequence[dict]:
    max_closed_for = timedelta(days=closed) if closed >= 0 else None
    geometry = parse_bbox(bbox)

    if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
        raise_for().notes_query_area_too_big()

    with joinedload_context(Note.comments, NoteComment.body_rich):
        notes = await NoteRepository.find_many_by_query(
            geometry=geometry,
            max_closed_for=max_closed_for,
            limit=limit,
        )

    await _resolve_rich_texts(notes)

    style = format_style()
    if style == FormatStyle.rss:
        min_lon, min_lat, max_lon, max_lat = geometry.bounds

        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))
        fg.subtitle(
            t('api.notes.rss.description_area').format(
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
            )
        )

        await Format06RSS.encode_notes(fg, notes)
        return fg.rss_str()

    else:
        return Format06.encode_notes(notes)


class SearchSort(StrEnum):
    created_at = 'created_at'
    updated_at = 'updated_at'


class SearchOrder(StrEnum):
    oldest = 'oldest'
    newest = 'newest'


@router.get('/notes/search')
@router.get('/notes/search.xml')
@router.get('/notes/search.json')
@router.get('/notes/search.rss')
@router.get('/notes/search.gpx', response_class=GPXResponse)
async def notes_query(
    request: Request,
    q: Annotated[str | None, Query(None)],
    closed: Annotated[float, Query(NOTE_QUERY_DEFAULT_CLOSED)],
    display_name: Annotated[str | None, Query(None, min_length=1)],
    user_id: Annotated[PositiveInt | None, Query(None, alias='user')],
    bbox: Annotated[str | None, Query(None, min_length=1)],
    from_: Annotated[datetime | None, DateValidator, Query(None, alias='from')],
    to: Annotated[datetime | None, DateValidator, Query(None)],
    sort: Annotated[SearchSort, Query(SearchSort.updated_at)],
    order: Annotated[SearchOrder, Query(SearchOrder.newest)],
    limit: Annotated[PositiveInt, Query(NOTE_QUERY_DEFAULT_LIMIT, le=NOTE_QUERY_LEGACY_MAX_LIMIT)],
) -> Sequence[dict]:
    # small logical optimization
    if from_ and to and from_ >= to:  # invalid date range
        return Format06.encode_notes([])
    if q is not None and not q.strip():  # provided empty q
        return Format06.encode_notes([])

    max_closed_for = timedelta(days=closed) if closed >= 0 else None

    if display_name:
        user = await UserRepository.find_one_by_display_name(display_name)
        if not user:
            raise_for().user_not_found_bad_request(display_name)
    elif user_id:
        user = await UserRepository.find_one_by_id(user_id)
        if not user:
            raise_for().user_not_found_bad_request(user_id)
    else:
        user = None

    if bbox:
        geometry = parse_bbox(bbox)

        if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
            raise_for().notes_query_area_too_big()
    else:
        geometry = None

    with joinedload_context(Note.comments, NoteComment.body_rich):
        notes = await NoteRepository.find_many_by_query(
            text=q,
            user_id=user.id if user else None,
            max_closed_for=max_closed_for,
            geometry=geometry,
            date_from=from_,
            date_to=to,
            sort_by_created=sort == SearchSort.created_at,
            sort_asc=order == SearchOrder.oldest,
            limit=limit,
        )

    await _resolve_rich_texts(notes)

    style = format_style()
    if style == FormatStyle.rss:
        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))

        if geometry:
            min_lon, min_lat, max_lon, max_lat = geometry.bounds
            fg.subtitle(
                t('api.notes.rss.description_area').format(
                    min_lon=min_lon,
                    min_lat=min_lat,
                    max_lon=max_lon,
                    max_lat=max_lat,
                )
            )
        else:
            fg.subtitle(t('api.notes.rss.description_all'))

        await Format06RSS.encode_notes(fg, notes)
        return fg.rss_str()

    else:
        return Format06.encode_notes(notes)
