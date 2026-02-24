from typing import Annotated

from fastapi import APIRouter, Path

from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_proto_page
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
        raise_for.user_not_found(display_name)

    return await render_proto_page(
        UserPage(user=user_proto(user)),
        title_prefix=t('notes.index.heading', user=user['display_name']),
    )
