from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request

from app.config import NOTE_USER_PAGE_SIZE
from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.queries.note_query import NoteQuery
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/user/{display_name:str}/notes')
@router.get('/user/{display_name:str}/notes/commented')
async def index(
    request: Request,
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
    status: Annotated[Literal['', 'open', 'closed'], Query()] = '',
):
    # active_tab, num_notes, notes_num_pages
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        raise_for.user_not_found(display_name)

    open = status == 'open' if status else None
    commented = request.url.path.endswith('/commented')

    notes_num_items = await NoteQuery.count_by_user(
        user['id'], commented_other=commented, open=open
    )
    notes_num_pages = ceil(notes_num_items / NOTE_USER_PAGE_SIZE)

    active_tab = 0 if not commented else 1

    return await render_response(
        'notes/index',
        {
            'profile': user,
            'active_tab': active_tab,
            'commented': commented,
            'status': status,
            'notes_num_items': notes_num_items,
            'notes_num_pages': notes_num_pages,
        },
    )
