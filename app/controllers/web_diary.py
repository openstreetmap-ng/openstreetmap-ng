from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, Query, Response
from pydantic import PositiveInt
from shapely import Point
from starlette import status

from app.config import (
    DIARY_BODY_MAX_LENGTH,
    DIARY_COMMENT_BODY_MAX_LENGTH,
    DIARY_TITLE_MAX_LENGTH,
    LOCALE_CODE_MAX_LENGTH,
)
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.diary_comment import diary_comments_resolve_rich_text
from app.models.db.user import User
from app.models.types import DiaryId, Latitude, LocaleCode, Longitude
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.user_query import UserQuery
from app.services.diary_comment_service import DiaryCommentService
from app.services.diary_service import DiaryService

router = APIRouter(prefix='/api/web/diary')


@router.post('')
async def create_or_update(
    user: Annotated[User, web_user()],
    title: Annotated[str, Form(min_length=1, max_length=DIARY_TITLE_MAX_LENGTH)],
    body: Annotated[str, Form(min_length=1, max_length=DIARY_BODY_MAX_LENGTH)],
    language: Annotated[LocaleCode, Form(min_length=1, max_length=LOCALE_CODE_MAX_LENGTH)],
    lon: Annotated[Longitude | None, Form()] = None,
    lat: Annotated[Latitude | None, Form()] = None,
    diary_id: Annotated[DiaryId | None, Form()] = None,
):
    lon_provided = lon is not None
    lat_provided = lat is not None
    if lon_provided != lat_provided:
        StandardFeedback.raise_error('lon' if lat_provided else 'lat', t('validation.incomplete_location_information'))
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


@router.get('/{diary_id:int}/comments')
async def comments_page(
    diary_id: DiaryId,
    page: Annotated[PositiveInt, Query()],
    num_items: Annotated[PositiveInt, Query()],
):
    comments = await DiaryCommentQuery.get_diary_page(diary_id, page=page, num_items=num_items)

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(diary_comments_resolve_rich_text(comments))

    return await render_response('diaries/comments_page.jinja2', {'comments': comments})


# TODO: delete comment
@router.post('/{diary_id:int}/comment')
async def create_comment(
    diary_id: DiaryId,
    body: Annotated[str, Form(min_length=1, max_length=DIARY_COMMENT_BODY_MAX_LENGTH)],
    _: Annotated[User, web_user()],
):
    await DiaryCommentService.comment(diary_id, body)
    return Response(None, status.HTTP_204_NO_CONTENT)
