from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Path
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import (
    DISPLAY_NAME_MAX_LENGTH,
)
from app.models.db.diary import Diary
from app.models.db.user import User
from app.models.types import DisplayNameType
from app.queries.diary_query import DiaryQuery

router = APIRouter()


@router.get('/user/{display_name:str}/diary/{diary_id:int}')
async def details(
    display_name: Annotated[DisplayNameType, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)],
    diary_id: PositiveInt,
):
    with options_context(
        joinedload(Diary.user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        diary = await DiaryQuery.find_one_by_id(diary_id)
    if diary is None:
        return await render_response(
            'diaries/not_found.jinja2',
            {'diary_id': diary_id},
            status=status.HTTP_404_NOT_FOUND,
        )
    if diary.user.display_name != display_name:
        return RedirectResponse(f'/user/{diary.user.display_name}/diary/{diary_id}', status.HTTP_302_FOUND)
    return await render_response('diaries/details.jinja2', {'diary': diary})
