from typing import Annotated

from fastapi import APIRouter, Form
from pydantic import PositiveInt

from app.lib.auth_context import web_user
from app.models.db.user import User
from app.models.geometry import Latitude, Longitude
from app.models.note_event import NoteEvent
from app.services.note_service import NoteService

router = APIRouter(prefix='/api/web/note')


# TODO: it is possible to use oauth to create user-authorized note
@router.post('/')
async def create_note(
    lon: Annotated[Longitude, Form()],
    lat: Annotated[Latitude, Form()],
    text: Annotated[str, Form(min_length=1)],
):
    note_id = await NoteService.create(lon, lat, text)
    return {'note_id': note_id}


@router.post('/{note_id:int}/comment')
async def create_note_comment(
    _: Annotated[User, web_user()],
    note_id: PositiveInt,
    event: Annotated[str, Form()],
    text: Annotated[str, Form(min_length=1)] = '',
):
    note_event: NoteEvent
    if event == 'closed':
        note_event = NoteEvent.closed
    elif event == 'reopened':
        note_event = NoteEvent.reopened
    elif event == 'commented':
        note_event = NoteEvent.commented
    else:
        raise NotImplementedError(f'Unsupported event {event!r}')
    await NoteService.comment(note_id, text, note_event)
    return {}
