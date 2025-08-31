from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Response
from starlette import status

from app.config import DISPLAY_NAME_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.types import UserId
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/admin/users/{user_id:int}')
async def user_edit(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    edit_user = await UserQuery.find_by_id(user_id)
    if edit_user is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    async with TaskGroup() as tg:
        connected_providers_task = tg.create_task(
            ConnectedAccountQuery.get_providers_by_user(user_id)
        )
        applications_task = tg.create_task(OAuth2ApplicationQuery.find_by_user(user_id))
        tokens_task = tg.create_task(OAuth2TokenQuery.find_pats_by_user(user_id))
        authorizations = await OAuth2TokenQuery.find_unique_per_app_by_user(user_id)
        tg.create_task(OAuth2ApplicationQuery.resolve_applications(authorizations))

    return await render_response(
        'admin/users/edit',
        {
            'edit_user': edit_user,
            'connected_providers': connected_providers_task.result(),
            'authorizations': authorizations,
            'applications': applications_task.result(),
            'tokens': tokens_task.result(),
            'DISPLAY_NAME_MAX_LENGTH': DISPLAY_NAME_MAX_LENGTH,
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        },
    )
