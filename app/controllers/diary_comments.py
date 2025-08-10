from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Path, Query
from starlette import status

from app.config import DIARY_COMMENTS_PAGE_SIZE
from app.lib.render_response import render_response
from app.models.db.diary_comment import diary_comments_resolve_rich_text
from app.models.types import DiaryCommentId
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/user/{display_name:str}/diary/comments')
async def user_diary_comments(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
    after: Annotated[DiaryCommentId | None, Query()] = None,
    before: Annotated[DiaryCommentId | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )
    user_id = user['id']

    comments = await DiaryCommentQuery.find_many_by_user(
        user_id=user_id,
        after=after,
        before=before,
        limit=DIARY_COMMENTS_PAGE_SIZE,
    )

    async def new_after_task():
        after = comments[0]['id']
        after_comments = await DiaryCommentQuery.find_many_by_user(
            user_id=user_id,
            after=after,
            limit=1,
        )
        return after if after_comments else None

    async def new_before_task():
        before = comments[-1]['id']
        before_comments = await DiaryCommentQuery.find_many_by_user(
            user_id=user_id,
            before=before,
            limit=1,
        )
        return before if before_comments else None

    new_after_t = None
    new_before_t = None

    if comments:
        async with TaskGroup() as tg:
            tg.create_task(DiaryQuery.resolve_diary(comments))
            tg.create_task(diary_comments_resolve_rich_text(comments))
            new_after_t = tg.create_task(new_after_task())
            new_before_t = tg.create_task(new_before_task())

    new_after = new_after_t.result() if new_after_t is not None else None
    new_before = new_before_t.result() if new_before_t is not None else None

    return await render_response(
        'diary/user-comments',
        {
            'profile': user,
            'new_after': new_after,
            'new_before': new_before,
            'comments': comments,
        },
    )
