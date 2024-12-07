from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request

from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.limits import DISPLAY_NAME_MAX_LENGTH, NOTE_USER_PAGE_SIZE
from app.models.types import DisplayNameType
from app.queries.note_query import NoteQuery
from app.queries.user_query import UserQuery

type _Status = Literal['', 'open', 'closed']

router = APIRouter()


@router.get('/user/{display_name:str}/notes')
@router.get('/user/{display_name:str}/notes/commented')
async def index(
    request: Request,
    display_name: Annotated[DisplayNameType, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)],
    status: Annotated[_Status, Query()] = '',
):
    # active_tab, num_notes, notes_num_pages
    user = await UserQuery.find_one_by_display_name(display_name)
    if user is None:
        raise_for.user_not_found(display_name)
    commented = request.url.path.endswith('/commented')
    open = None if status == '' else (status == 'open')
    notes_num_items = await NoteQuery.count_by_user_id(user.id, commented_other=commented, open=open)
    notes_num_pages = ceil(notes_num_items / NOTE_USER_PAGE_SIZE)
    active_tab = 0 if not commented else 1
    return await render_response(
        'notes/index.jinja2',
        {
            'profile': user,
            'active_tab': active_tab,
            'commented': commented,
            'status': status,
            'notes_num_items': notes_num_items,
            'notes_num_pages': notes_num_pages,
        },
    )
