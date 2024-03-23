from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated

from anyio import create_task_group
from fastapi import APIRouter, Query, Request
from feedgen.feed import FeedGenerator
from pydantic import PositiveInt
from shapely import Point

from app.format06 import Format06, FormatRSS06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_rss
from app.lib.geo_utils import parse_bbox
from app.lib.statement_context import joinedload_context
from app.lib.translation import t
from app.limits import (
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_DEFAULT_LIMIT,
    NOTE_QUERY_LEGACY_MAX_LIMIT,
)
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.db.user import User
from app.models.geometry import Latitude, Longitude
from app.models.note_event import NoteEvent
from app.models.scope import ExtendedScope, Scope
from app.repositories.note_comment_repository import NoteCommentRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.user_repository import UserRepository
from app.responses.osm_response import GPXResponse
from app.services.note_service import NoteService
from app.validators.date import DateValidator

router = APIRouter()

# TODO: validate input lengths


async def _resolve_comments_and_rich_text(notes_or_comments: Sequence[Note | NoteComment]) -> None:
    """
    Resolve note comments and their rich text.
    """
    # small optimization
    if not notes_or_comments:
        return

    async with create_task_group() as tg:
        # is it a sequence of comments or notes?
        if isinstance(notes_or_comments[0], NoteComment):
            comment: NoteComment
            for comment in notes_or_comments:
                tg.start_soon(comment.resolve_rich_text)
        else:
            with joinedload_context(NoteComment.user):
                await NoteCommentRepository.resolve_comments(notes_or_comments, limit_per_note=None)
            note: Note
            for note in notes_or_comments:
                for comment in note.comments:
                    tg.start_soon(comment.resolve_rich_text)


@router.post('/notes')
@router.post('/notes.xml')
@router.post('/notes.json')
@router.post('/notes.gpx', response_class=GPXResponse)
async def note_create(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    text: Annotated[str, Query(min_length=1)],
) -> dict:
    point = Point(lon, lat)
    note_id = await NoteService.create(point, text)
    notes = await NoteRepository.find_many_by_query(note_ids=(note_id,), limit=1)
    await _resolve_comments_and_rich_text(notes)
    return Format06.encode_note(notes[0])


@router.get('/notes/{note_id:int}')
@router.get('/notes/{note_id:int}.xml')
@router.get('/notes/{note_id:int}.json')
@router.get('/notes/{note_id:int}.rss')
@router.get('/notes/{note_id:int}.gpx', response_class=GPXResponse)
async def note_read(
    request: Request,
    note_id: PositiveInt,
) -> dict:
    notes = await NoteRepository.find_many_by_query(note_ids=(note_id,), limit=1)

    if not notes:
        raise_for().note_not_found(note_id)

    await _resolve_comments_and_rich_text(notes)

    if format_is_rss():
        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))
        fg.subtitle(t('api.notes.rss.description_item').format(id=note_id))

        await FormatRSS06.encode_notes(fg, notes)
        return fg.rss_str()

    else:
        return Format06.encode_note(notes[0])


@router.post('/notes/{note_id:int}/comment')
@router.post('/notes/{note_id:int}/comment.xml')
@router.post('/notes/{note_id:int}/comment.json')
@router.post('/notes/{note_id:int}/comment.gpx', response_class=GPXResponse)
async def note_comment(
    note_id: PositiveInt,
    text: Annotated[str, Query(min_length=1)],
    _: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    await NoteService.comment(note_id, text, NoteEvent.commented)
    notes = await NoteRepository.find_many_by_query(note_ids=(note_id,), limit=1)
    await _resolve_comments_and_rich_text(notes)
    return Format06.encode_note(notes[0])


@router.post('/notes/{note_id:int}/close')
@router.post('/notes/{note_id:int}/close.xml')
@router.post('/notes/{note_id:int}/close.json')
@router.post('/notes/{note_id:int}/close.gpx', response_class=GPXResponse)
async def note_close(
    _: Annotated[User, api_user(Scope.write_notes)],
    note_id: PositiveInt,
    text: Annotated[str, Query()] = '',
) -> dict:
    await NoteService.comment(note_id, text, NoteEvent.closed)
    notes = await NoteRepository.find_many_by_query(note_ids=(note_id,), limit=1)
    await _resolve_comments_and_rich_text(notes)
    return Format06.encode_note(notes[0])


@router.post('/notes/{note_id:int}/reopen')
@router.post('/notes/{note_id:int}/reopen.xml')
@router.post('/notes/{note_id:int}/reopen.json')
@router.post('/notes/{note_id:int}/reopen.gpx', response_class=GPXResponse)
async def note_reopen(
    _: Annotated[User, api_user(Scope.write_notes)],
    note_id: PositiveInt,
    text: Annotated[str, Query()] = '',
) -> dict:
    await NoteService.comment(note_id, text, NoteEvent.reopened)
    notes = await NoteRepository.find_many_by_query(note_ids=(note_id,), limit=1)
    await _resolve_comments_and_rich_text(notes)
    return Format06.encode_note(notes[0])


@router.delete('/notes/{note_id:int}')
@router.delete('/notes/{note_id:int}.xml')
@router.delete('/notes/{note_id:int}.json')
@router.delete('/notes/{note_id:int}.gpx', response_class=GPXResponse)
async def note_hide(
    _: Annotated[User, api_user(Scope.write_notes, ExtendedScope.role_moderator)],
    note_id: PositiveInt,
    text: Annotated[str, Query()] = '',
) -> dict:
    await NoteService.comment(note_id, text, NoteEvent.hidden)
    notes = await NoteRepository.find_many_by_query(note_ids=(note_id,), limit=1)
    await _resolve_comments_and_rich_text(notes)
    return Format06.encode_note(notes[0])


@router.get('/notes/feed')
@router.get('/notes/feed.rss')
async def notes_feed(
    request: Request,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
) -> Sequence[dict]:
    if bbox is not None:
        geometry = parse_bbox(bbox)
        if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
            raise_for().notes_query_area_too_big()
    else:
        geometry = None

    with joinedload_context(NoteComment.user, NoteComment.legacy_note):
        comments = await NoteCommentRepository.legacy_find_many_by_query(
            geometry=geometry,
            limit=NOTE_QUERY_DEFAULT_LIMIT,
        )

    # small optimization, skip processing for empty result
    # deduplicate legacy_note instances and resolve rich text
    if comments:
        note_id_map = {}
        notes = []
        for comment in comments:
            note = note_id_map.get(comment.note_id)
            if note is not None:
                comment.legacy_note = note
            else:
                note = comment.legacy_note
                note_id_map[comment.note_id] = note
                notes.append(note)

        async with create_task_group() as tg:
            tg.start_soon(_resolve_comments_and_rich_text(comments))
            tg.start_soon(_resolve_comments_and_rich_text(notes))

    fg = FeedGenerator()
    fg.link(href=str(request.url), rel='self')
    fg.title(t('api.notes.rss.title'))

    if geometry is not None:
        minx, miny, maxx, maxy = geometry.bounds  # TODO: MultiPolygon support

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
async def notes_read(
    request: Request,
    bbox: Annotated[str, Query()],
    closed: Annotated[int, Query()] = NOTE_QUERY_DEFAULT_CLOSED,
    limit: Annotated[PositiveInt, Query(le=NOTE_QUERY_LEGACY_MAX_LIMIT)] = NOTE_QUERY_DEFAULT_LIMIT,
) -> Sequence[dict]:
    max_closed_for = timedelta(days=closed) if closed >= 0 else None
    geometry = parse_bbox(bbox)
    if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
        raise_for().notes_query_area_too_big()

    notes = await NoteRepository.find_many_by_query(
        geometry=geometry,
        max_closed_for=max_closed_for,
        limit=limit,
    )

    await _resolve_comments_and_rich_text(notes)

    if format_is_rss():
        minx, miny, maxx, maxy = geometry.bounds  # TODO: MultiPolygon support

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

    else:
        return Format06.encode_notes(notes)


class _SearchSort(str, Enum):
    created_at = 'created_at'
    updated_at = 'updated_at'


class _SearchOrder(str, Enum):
    oldest = 'oldest'
    newest = 'newest'


@router.get('/notes/search')
@router.get('/notes/search.xml')
@router.get('/notes/search.json')
@router.get('/notes/search.rss')
@router.get('/notes/search.gpx', response_class=GPXResponse)
async def notes_query(
    request: Request,
    q: Annotated[str | None, Query()] = None,
    closed: Annotated[float, Query()] = NOTE_QUERY_DEFAULT_CLOSED,
    display_name: Annotated[str | None, Query(min_length=1)] = None,
    user_id: Annotated[PositiveInt | None, Query(alias='user')] = None,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    from_: Annotated[datetime | None, DateValidator, Query(alias='from')] = None,
    to: Annotated[datetime | None, DateValidator, Query()] = None,
    sort: Annotated[_SearchSort, Query()] = _SearchSort.updated_at,
    order: Annotated[_SearchOrder, Query()] = _SearchOrder.newest,
    limit: Annotated[PositiveInt, Query(le=NOTE_QUERY_LEGACY_MAX_LIMIT)] = NOTE_QUERY_DEFAULT_LIMIT,
) -> Sequence[dict]:
    # small logical optimizations
    if (from_ is not None) and (to is not None) and (from_ >= to):  # invalid date range
        return Format06.encode_notes(())
    if (q is not None) and (not q.strip()):  # provided empty q
        return Format06.encode_notes(())

    max_closed_for = timedelta(days=closed) if closed >= 0 else None

    if display_name is not None:
        user = await UserRepository.find_one_by_display_name(display_name)
        if user is None:
            raise_for().user_not_found_bad_request(display_name)
    elif user_id is not None:
        user = await UserRepository.find_one_by_id(user_id)
        if user is None:
            raise_for().user_not_found_bad_request(user_id)
    else:
        user = None

    if bbox is not None:
        geometry = parse_bbox(bbox)
        if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
            raise_for().notes_query_area_too_big()
    else:
        geometry = None

    notes = await NoteRepository.find_many_by_query(
        text=q,
        user_id=user.id if user is not None else None,
        max_closed_for=max_closed_for,
        geometry=geometry,
        date_from=from_,
        date_to=to,
        sort_by_created=sort == _SearchSort.created_at,
        sort_asc=order == _SearchOrder.oldest,
        limit=limit,
    )

    await _resolve_comments_and_rich_text(notes)

    if format_is_rss():
        fg = FeedGenerator()
        fg.link(href=str(request.url), rel='self')
        fg.title(t('api.notes.rss.title'))

        if geometry is not None:
            minx, miny, maxx, maxy = geometry.bounds  # TODO: MultiPolygon support

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

    else:
        return Format06.encode_notes(notes)
