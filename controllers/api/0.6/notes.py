from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import PositiveInt
from shapely.geometry import Point

from geoutils import parse_bbox
from lib.auth import api_user, auth_user
from lib.exceptions import raise_for
from lib.format.format06 import Format06
from limits import (
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_CLOSED,
    NOTE_QUERY_DEFAULT_LIMIT,
    NOTE_QUERY_LEGACY_MAX_LIMIT,
)
from models.db.note import Note
from models.db.note_comment import NoteComment
from models.db.user import User
from models.geometry import Latitude, Longitude
from models.note_event import NoteEvent
from models.scope import ExtendedScope, Scope
from models.str import NonEmptyStr, UserNameStr

router = APIRouter()

# TODO: The output can be in several formats (e.g. XML, RSS, json or GPX) depending on the file extension.


@router.get('/notes/{note_id}')
@router.get('/notes/{note_id}.xml')
@router.get('/notes/{note_id}.json')
async def note_read(
    note_id: PositiveInt,
) -> dict:
    note = await Note.find_one_by_id(note_id)

    if note is None or not note.visible_to(auth_user()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return Format06.encode_note(note)


@router.post('/notes')
async def note_create(
    request: Request,
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    text: Annotated[NonEmptyStr, Query()],
) -> dict:
    if user := auth_user():
        user_id = user.id
        user_ip = None
    else:
        user_id = None
        user_ip = request.client.host

    note = Note(point=Point(lon, lat))
    comment = NoteComment(user_id=user_id, user_ip=user_ip, event=NoteEvent.opened, body=text)

    await note.create_with_comment(comment)
    note.comments_ = (comment,)
    return Format06.encode_note(note)


@retry_transaction()
@router.post('/notes/{note_id}/comment')
async def note_comment(
    note_id: PositiveInt,
    text: Annotated[NonEmptyStr, Query()],
    user: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    note = await Note.find_one_by_id(note_id)
    if note is None or not note.visible_to(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if note.closed_at:
        raise_for().note_closed(note_id, note.closed_at)

    comment = NoteComment(note_id=note_id, user_id=user.id, user_ip=None, event=NoteEvent.commented, body=text)

    async with Transaction() as session:
        await comment.create(session=session)
        await note.update({'closed_at': None}, session=session)

    note.comments_ = NoteComment.find_many_by_note_id(note_id, sort={'created_at': DESCENDING}, limit=None)
    return Format06.encode_note(note)


@retry_transaction()
@router.post('/notes/{note_id}/close')
async def note_close(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    user: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    note = await Note.find_one_by_id(note_id)
    if note is None or not note.visible_to(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if note.closed_at:
        raise_for().note_closed(note_id, note.closed_at)

    comment = NoteComment(note_id=note_id, user_id=user.id, user_ip=None, event=NoteEvent.closed, body=text)

    async with Transaction() as session:
        await comment.create(session=session)
        note.closed_at = comment.created_at  # TODO: created_at during create
        await note.update({'closed_at': None}, session=session)

    note.comments_ = NoteComment.find_many_by_note_id(note_id, sort={'created_at': DESCENDING}, limit=None)
    return Format06.encode_note(note)


@retry_transaction()
@router.post('/notes/{note_id}/reopen')
async def note_reopen(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    user: Annotated[User, api_user(Scope.write_notes)],
) -> dict:
    note = await Note.find_one_by_id(note_id)
    if note is None or not note.visible_to(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    comment = NoteComment(note_id=note_id, user_id=user.id, user_ip=None, event=NoteEvent.reopened, body=text)

    if note.hidden_at:
        # unhide
        async with Transaction() as session:
            await comment.create(session=session)
            prev_hidden_at = note.hidden_at
            note.hidden_at = None
            await note.update({'hidden_at': prev_hidden_at}, session=session)
    else:
        # reopen
        if not note.closed_at:
            raise_for().note_open(note_id)

        async with Transaction() as session:
            await comment.create(session=session)
            prev_hidden_at = note.closed_at
            note.closed_at = None
            await note.update({'closed_at': prev_hidden_at}, session=session)

    # TODO: check find_many limits in 0.6
    note.comments_ = NoteComment.find_many_by_note_id(note_id, sort={'created_at': DESCENDING}, limit=None)
    return Format06.encode_note(note)


@retry_transaction()
@router.delete('/notes/{note_id}')
async def note_hide(
    note_id: PositiveInt,
    text: Annotated[str, Query('')],
    user: Annotated[User, api_user(Scope.write_notes, ExtendedScope.role_moderator)],
) -> dict:
    note = await Note.find_one_by_id(note_id)
    if note is None or not note.visible_to(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if note.hidden_at:
        raise HTTPException(status_code=status.HTTP_410_GONE)

    comment = NoteComment(note_id=note_id, user_id=user.id, user_ip=None, event=NoteEvent.hidden, body=text)

    async with Transaction() as session:
        await comment.create(session=session)
        note.hidden_at = comment.created_at
        await note.update({'hidden_at': None}, session=session)

    note.comments_ = NoteComment.find_many_by_note_id(note_id, sort={'created_at': DESCENDING}, limit=None)
    return Format06.encode_note(note)


@router.get('/notes')
@router.get('/notes.xml')
@router.get('/notes.json')
async def notes_read(
    bbox: Annotated[NonEmptyStr, Query()],
    limit: Annotated[PositiveInt, Query(NOTE_QUERY_DEFAULT_LIMIT, le=NOTE_QUERY_LEGACY_MAX_LIMIT)],
    closed: Annotated[int, Query(NOTE_QUERY_DEFAULT_CLOSED)],
) -> Sequence[dict]:
    geometry = parse_bbox(bbox)
    if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
        raise_for().notes_query_area_too_big()

    max_closed_for = timedelta(days=closed) if closed >= 0 else None
    notes, _ = await Note.find_many_by_geometry_with_(
        cursor=None, geometry=geometry, max_closed_for=max_closed_for, limit=limit
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
async def note_search(
    q: Annotated[NonEmptyStr | None, Query(None)],
    limit: Annotated[PositiveInt, Query(NOTE_QUERY_DEFAULT_LIMIT, le=NOTE_QUERY_LEGACY_MAX_LIMIT)],
    closed: Annotated[int, Query(NOTE_QUERY_DEFAULT_CLOSED)],
    display_name: Annotated[UserNameStr | None, Query(None)],
    user_id: Annotated[PositiveInt | None, Query(None, alias='user')],
    bbox: Annotated[NonEmptyStr | None, Query(None)],
    from_: Annotated[datetime | None, Query(None, alias='from')],
    to: Annotated[datetime | None, Query(None)],
    sort: Annotated[SearchSort, Query(SearchSort.updated_at)],
    order: Annotated[SearchOrder, Query(SearchOrder.newest)],
) -> Sequence[dict]:
    if display_name:
        user = await User.find_one_by_display_name(display_name)
        if not user:
            raise_for().user_not_found(display_name)
    elif user_id:
        user = await User.find_one_by_id(user_id)
        if not user:
            raise_for().user_not_found(user)
    else:
        user = None

    if bbox:
        geometry = parse_bbox(bbox)
        if geometry.area > NOTE_QUERY_AREA_MAX_SIZE:
            raise_for().notes_query_area_too_big()
    else:
        geometry = None

    if from_ and to and from_ >= to:
        return ()

    max_closed_for = timedelta(days=closed) if closed >= 0 else None
    notes = await Note.find_many_by_search_with_(
        geometry=geometry,
        max_closed_for=max_closed_for,
        q=q,
        user_id=user.id if user else None,
        from_=from_,
        to=to,
        sort={sort.value: DESCENDING if order == SearchOrder.newest else ASCENDING},
        limit=limit,
    )

    return Format06.encode_notes(notes)
