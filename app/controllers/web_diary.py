from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Response
from psycopg.sql import SQL
from shapely import Point
from starlette import status

from app.config import (
    DIARY_BODY_MAX_LENGTH,
    DIARY_COMMENT_BODY_MAX_LENGTH,
    DIARY_COMMENTS_PAGE_SIZE,
    DIARY_LIST_PAGE_SIZE,
    DIARY_TITLE_MAX_LENGTH,
    LOCALE_CODE_MAX_LENGTH,
)
from app.lib.auth_context import web_user
from app.lib.locale import LOCALES_NAMES_MAP, normalize_locale
from app.lib.standard_feedback import StandardFeedback
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response,
)
from app.lib.translation import t
from app.models.db.diary import Diary, diaries_resolve_rich_text
from app.models.db.diary_comment import DiaryComment, diary_comments_resolve_rich_text
from app.models.db.user import User
from app.models.types import DiaryId, Latitude, LocaleCode, Longitude, UserId
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.diary_comment_service import DiaryCommentService
from app.services.diary_service import DiaryService

router = APIRouter(prefix='/api/web/diary')


@router.post('')
async def create_or_update(
    user: Annotated[User, web_user()],
    title: Annotated[str, Form(min_length=1, max_length=DIARY_TITLE_MAX_LENGTH)],
    body: Annotated[str, Form(min_length=1, max_length=DIARY_BODY_MAX_LENGTH)],
    language: Annotated[
        LocaleCode, Form(min_length=1, max_length=LOCALE_CODE_MAX_LENGTH)
    ],
    lon: Annotated[Longitude | None, Form()] = None,
    lat: Annotated[Latitude | None, Form()] = None,
    diary_id: Annotated[DiaryId | None, Form()] = None,
):
    lon_provided = lon is not None
    lat_provided = lat is not None
    if lon_provided != lat_provided:
        StandardFeedback.raise_error(
            'lon' if lat_provided else 'lat',
            t('validation.incomplete_location_information'),
        )
    point = Point(lon, lat) if (lon_provided and lat_provided) else None

    if diary_id is None:
        diary_id = await DiaryService.create(
            title=title,
            body=body,
            language=language,
            point=point,
        )
    else:
        await DiaryService.update(
            diary_id=diary_id,
            title=title,
            body=body,
            language=language,
            point=point,
        )

    return {'redirect_url': f'/user/{user["display_name"]}/diary/{diary_id}'}


@router.post('/{diary_id:int}/delete')
async def delete(
    user: Annotated[User, web_user()],
    diary_id: DiaryId,
):
    await DiaryService.delete(diary_id)
    return {'redirect_url': f'/user/{user["display_name"]}/diary'}


@router.post('/{diary_id:int}/comments')
async def comments_page(
    diary_id: DiaryId,
    sp_state: StandardPaginationStateBody = b'',
):
    comments, state = await sp_paginate_table(
        DiaryComment,
        sp_state,
        table='diary_comment',
        where=SQL('diary_id = %s'),
        params=(diary_id,),
        page_size=DIARY_COMMENTS_PAGE_SIZE,
        order_dir='desc',
        display_dir='asc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(diary_comments_resolve_rich_text(comments))

    return await sp_render_response(
        'diary/comments-page',
        {'comments': comments},
        state,
    )


# TODO: delete comment
@router.post('/{diary_id:int}/comment')
async def create_comment(
    diary_id: DiaryId,
    body: Annotated[str, Form(min_length=1, max_length=DIARY_COMMENT_BODY_MAX_LENGTH)],
    _: Annotated[User, web_user()],
):
    await DiaryCommentService.comment(diary_id, body)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/page')
async def diaries_page(
    user_id: Annotated[UserId | None, Query()] = None,
    language: Annotated[LocaleCode | None, Query()] = None,
    sp_state: StandardPaginationStateBody = b'',
):
    language = normalize_locale(language)
    if user_id is not None and language is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            'Only one of user_id and language can be set',
        )

    where = SQL('TRUE')
    params: tuple[object, ...] = ()
    if user_id is not None:
        where = SQL('user_id = %s')
        params = (user_id,)
    elif language is not None:
        where = SQL('language = %s')
        params = (language,)

    diaries, state = await sp_paginate_table(
        Diary,
        sp_state,
        table='diary',
        where=where,
        params=params,
        page_size=DIARY_LIST_PAGE_SIZE,
        cursor_column='id',
        cursor_kind='id',
        order_dir='desc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(diaries))
        tg.create_task(diaries_resolve_rich_text(diaries))
        tg.create_task(DiaryQuery.resolve_location_name(diaries))
        tg.create_task(DiaryCommentQuery.resolve_num_comments(diaries))
        tg.create_task(UserSubscriptionQuery.resolve_is_subscribed('diary', diaries))

    return await sp_render_response(
        'diary/page',
        {
            'diaries': diaries,
            'profile': True if user_id is not None else None,
            'LOCALES_NAMES_MAP': LOCALES_NAMES_MAP,
            'DIARY_COMMENT_BODY_MAX_LENGTH': DIARY_COMMENT_BODY_MAX_LENGTH,
        },
        state,
    )


@router.post('/user/{user_id:int}/comments')
async def user_comments_page(
    user_id: UserId,
    sp_state: StandardPaginationStateBody = b'',
):
    comments, state = await sp_paginate_table(
        DiaryComment,
        sp_state,
        table='diary_comment',
        where=SQL('user_id = %s'),
        params=(user_id,),
        page_size=DIARY_COMMENTS_PAGE_SIZE,
        cursor_column='id',
        cursor_kind='id',
        order_dir='desc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(DiaryQuery.resolve_diary(comments))
        tg.create_task(diary_comments_resolve_rich_text(comments))

    return await sp_render_response(
        'diary/user-comments-page',
        {'comments': comments},
        state,
    )
