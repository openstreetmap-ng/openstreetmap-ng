from typing import Annotated

from fastapi import APIRouter, Path
from starlette import status

from app.lib.render_response import render_proto_page, render_response
from app.lib.translation import t
from app.models.db.user import user_proto
from app.models.proto.note_pb2 import UserPage
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
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )

    return await render_proto_page(
        UserPage(user=user_proto(user)),
        title_prefix=t('notes.index.heading', user=user['display_name']),
    )
