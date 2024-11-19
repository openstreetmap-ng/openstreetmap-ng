from typing import Annotated

from fastapi import APIRouter
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import web_user
from app.lib.locale import LOCALES_NAMES_MAP
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import (
    DIARY_BODY_MAX_LENGTH,
    DIARY_TITLE_MAX_LENGTH,
)
from app.models.db.diary import Diary
from app.models.db.user import User
from app.queries.diary_query import DiaryQuery

router = APIRouter()


@router.get('/diary/{diary_id:int}')
async def details(diary_id: PositiveInt):
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
    return await render_response('diaries/details.jinja2', {'diary': diary})


@router.get('/diary/{diary_id:int}/edit')
async def edit(
    user: Annotated[User, web_user()],
    diary_id: PositiveInt,
):
    diary = await DiaryQuery.find_one_by_id(diary_id)
    if diary is None or diary.user_id != user.id:
        return render_response(
            'diaries/not_found.jinja2',
            {'diary_id': diary_id},
            status=status.HTTP_404_NOT_FOUND,
        )
    point = diary.point
    return await render_response(
        'diaries/compose.jinja2',
        {
            'new': False,
            'LOCALES_NAMES_MAP': LOCALES_NAMES_MAP,
            'DIARY_TITLE_MAX_LENGTH': DIARY_TITLE_MAX_LENGTH,
            'DIARY_BODY_MAX_LENGTH': DIARY_BODY_MAX_LENGTH,
            'title': diary.title,
            'body': diary.body,
            'language': diary.language,
            'lon': point.x if (point is not None) else '',
            'lat': point.y if (point is not None) else '',
            'diary_id': diary_id,
        },
    )


@router.get('/user/{_:str}/diary/{diary_id:int}{suffix:path}')
async def legacy_user_diary(diary_id: PositiveInt, suffix: str):
    return RedirectResponse(f'/diary/{diary_id}{suffix}', status.HTTP_301_MOVED_PERMANENTLY)
