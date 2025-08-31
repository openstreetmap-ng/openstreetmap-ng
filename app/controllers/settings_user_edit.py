from typing import Annotated

from fastapi import APIRouter, Response
from starlette import status

from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.types import UserId
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/settings/users/{user_id:int}')
async def user_edit(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    edit_user = await UserQuery.find_by_id(user_id)
    if edit_user is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    connected_providers = await ConnectedAccountQuery.get_providers_by_user(user_id)

    return await render_response(
        'settings/users/edit',
        {
            'edit_user': edit_user,
            'connected_providers': connected_providers,
        },
    )
