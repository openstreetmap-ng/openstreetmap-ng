from typing import Annotated

from fastapi import APIRouter, Form

from app.models.geometry import Latitude, Longitude
from app.services.note_service import NoteService

router = APIRouter(prefix='/api/web')


@router.post('/note')
async def create_note(
    lon: Annotated[Longitude, Form()],
    lat: Annotated[Latitude, Form()],
    text: Annotated[str, Form(min_length=1)],
):
    note_id = await NoteService.create(lon, lat, text)
    return {'note_id': note_id}
