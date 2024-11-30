from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status

from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import DIARY_COMMENTS_PAGE_SIZE, DISPLAY_NAME_MAX_LENGTH
from app.models.db.diary import Diary
from app.models.db.diary_comment import DiaryComment
from app.models.types import DisplayNameType
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/user/{display_name:str}/diary/comments')
async def user_diary_comments(
    display_name: Annotated[DisplayNameType, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not_found.jinja2',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )

    with options_context(joinedload(DiaryComment.diary).load_only(Diary.title)):
        comments = await DiaryCommentQuery.find_many_by_user_id(
            user_id=user.id,
            after=after,
            before=before,
            limit=DIARY_COMMENTS_PAGE_SIZE,
        )

    async def new_after_task():
        after = comments[0].id
        after_comments = await DiaryCommentQuery.find_many_by_user_id(
            user_id=user.id,
            after=after,
            limit=1,
        )
        return after if after_comments else None

    async def new_before_task():
        before = comments[-1].id
        before_comments = await DiaryCommentQuery.find_many_by_user_id(
            user_id=user.id,
            before=before,
            limit=1,
        )
        return before if before_comments else None

    new_after_t = None
    new_before_t = None
    if comments:
        async with TaskGroup() as tg:
            for comment in comments:
                tg.create_task(comment.resolve_rich_text())
            new_after_t = tg.create_task(new_after_task())
            new_before_t = tg.create_task(new_before_task())
    new_after = new_after_t.result() if (new_after_t is not None) else None
    new_before = new_before_t.result() if (new_before_t is not None) else None

    return await render_response(
        'diaries/user_comments.jinja2',
        {
            'profile': user,
            'new_after': new_after,
            'new_before': new_before,
            'comments': comments,
        },
    )
