from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import PositiveInt
from shapely.geometry import Point

from cython_lib.geoutils import parse_bbox
from lib.auth import api_user
from lib.exceptions import raise_for
from lib.format.format06 import Format06
from limits import (
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_DEFAULT_LIMIT,
    NOTE_QUERY_LEGACY_MAX_LIMIT,
)
from models.db.user import User
from models.geometry import Latitude, Longitude
from models.note_event import NoteEvent
from models.scope import ExtendedScope, Scope
from repositories.note_repository import NoteRepository
from repositories.user_repository import UserRepository
from services.note_service import NoteService
from validators.date import DateValidator

router = APIRouter()

# TODO: The output can be in several formats (e.g. XML, RSS, json or GPX) depending on the file extension.
# TODO: validate input lengths


@router.post('/notes')
async def note_create(
    request: Request,
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    text: Annotated[str, Query(min_length=1)],
) -> dict:
    point = Point(lon, lat)
    note = await NoteService.create(request, point, text)
    return Format06.encode_note(note)


@router.get('/notes/{note_id}')
@router.get('/notes/{note_id}.xml')
@router.get('/notes/{note_id}.json')
async def note_read(
    note_id: PositiveInt,
) -> dict:
    notes = await NoteRepository.find_many_by_query(note_ids=[note_id], limit=None)

    if not notes:
        raise_for().note_not_found(note_id)

    return Format06.encode_note(notes[0])


@router.post('/notes/{note_id}/comment')
async def note_comment(
    note_id: PositiveInt,
    text: Annotated[str, Query(min_length=1)],
    _: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    note = await NoteService.comment(note_id, text, NoteEvent.commented)
    return Format06.encode_note(note)


@router.post('/notes/{note_id}/close')
async def note_close(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    _: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    note = await NoteService.comment(note_id, text, NoteEvent.closed)
    return Format06.encode_note(note)


@router.post('/notes/{note_id}/reopen')
async def note_reopen(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    _: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    note = await NoteService.comment(note_id, text, NoteEvent.reopened)
    return Format06.encode_note(note)


@router.delete('/notes/{note_id}')
async def note_hide(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    _: Annotated[User, api_user(Scope.write_notes, ExtendedScope.role_moderator)],
) -> dict:
    note = await NoteService.comment(note_id, text, NoteEvent.hidden)
    return Format06.encode_note(note)


@router.get('/notes')
@router.get('/notes.xml')
@router.get('/notes.json')
async def notes_read(
    bbox: Annotated[str, Query(min_length=1)],
    closed: Annotated[int, Query(NOTE_QUERY_DEFAULT_CLOSED)],
    limit: Annotated[PositiveInt, Query(NOTE_QUERY_DEFAULT_LIMIT, le=NOTE_QUERY_LEGACY_MAX_LIMIT)],
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
async def notes_query(
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

    return Format06.encode_notes(notes)
