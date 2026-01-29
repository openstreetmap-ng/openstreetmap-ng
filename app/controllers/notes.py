from typing import Annotated

from fastapi import APIRouter, Path

from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/user/{display_name:str}/notes')
@router.get('/user/{display_name:str}/notes/commented')
async def index(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        raise_for.user_not_found(display_name)

    return await render_response('notes/index', {'profile': user})
