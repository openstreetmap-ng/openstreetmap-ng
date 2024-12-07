from asyncio import TaskGroup
from collections.abc import Sequence
from math import ceil
from typing import Annotated

from fastapi import APIRouter
from pydantic import PositiveInt
from starlette import status
from starlette.responses import RedirectResponse

from app.controllers.diaries import get_diaries_data
from app.lib.auth_context import web_user
from app.lib.locale import LOCALES_NAMES_MAP
from app.lib.render_response import render_response
from app.limits import (
    DIARY_BODY_MAX_LENGTH,
    DIARY_COMMENT_BODY_MAX_LENGTH,
    DIARY_COMMENTS_PAGE_SIZE,
    DIARY_TITLE_MAX_LENGTH,
)
from app.models.db.diary import Diary
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.queries.diary_query import DiaryQuery
from app.queries.user_subscription_query import UserSubscriptionQuery

router = APIRouter()


@router.get('/diary/{diary_id:int}')
async def details(diary_id: PositiveInt):
    async with TaskGroup() as tg:
        is_subscribed_t = tg.create_task(UserSubscriptionQuery.is_subscribed(UserSubscriptionTarget.diary, diary_id))
        data = await get_diaries_data(
            user=None,
            language=None,
            after=diary_id - 1,
            before=diary_id + 1,
            user_from_diary=True,
            with_navigation=False,
        )
        diaries: Sequence[Diary] = data['diaries']
        diary = diaries[0] if diaries else None
        if diary is None:
            return await render_response(
                'diaries/not_found.jinja2',
                {'diary_id': diary_id},
                status=status.HTTP_404_NOT_FOUND,
            )
    if diary.num_comments is None:
        raise AssertionError('Diary num comments must be set')
    diary_comments_num_items = diary.num_comments
    diary_comments_num_pages = ceil(diary_comments_num_items / DIARY_COMMENTS_PAGE_SIZE)
    return await render_response(
        'diaries/details.jinja2',
        {
            **data,
            'diary': diary,
            'is_subscribed': is_subscribed_t.result(),
            'diary_comments_num_items': diary_comments_num_items,
            'diary_comments_num_pages': diary_comments_num_pages,
            'DIARY_COMMENT_BODY_MAX_LENGTH': DIARY_COMMENT_BODY_MAX_LENGTH,
        },
    )


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
