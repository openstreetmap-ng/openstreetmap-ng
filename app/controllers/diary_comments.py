from typing import Annotated

from fastapi import APIRouter, Path
from starlette import status

from app.lib.render_response import render_response
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/user/{display_name:str}/diary/comments')
async def user_diary_comments(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )

    return await render_response(
        'diary/user-comments',
        {
            'profile': user,
        },
    )
