from typing import Annotated

import numpy as np
from fastapi import APIRouter, Query, Response, status

from app.format import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.models.db.user import User, UserId
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/api/0.6')


@router.get('/user/details')
@router.get('/user/details.xml')
@router.get('/user/details.json')
async def get_current_user(
    user: Annotated[User, api_user()],
):
    return await Format06.encode_user(user)


@router.get('/user/{user_id:int}')
@router.get('/user/{user_id:int}.xml')
@router.get('/user/{user_id:int}.json')
async def get_user(
    user_id: UserId,
):
    user = await UserQuery.find_one_by_id(user_id)
    if user is None:
        raise_for.user_not_found(user_id)
    if False:  # TODO: if user deleted
        return Response(None, status.HTTP_410_GONE)

    return await Format06.encode_user(user)


@router.get('/users')
@router.get('/users.xml')
@router.get('/users.json')
async def get_many_users(
    query: Annotated[str, Query(alias='users', min_length=1)],
):
    try:
        ids = np.fromstring(query, np.uint64, sep=',')
    except ValueError:
        return Response('Users query must be a comma-separated list of integers', status.HTTP_400_BAD_REQUEST)
    if not ids.size:
        return Response('No users were given to search for', status.HTTP_400_BAD_REQUEST)

    user_ids: list[UserId] = ids.tolist()  # type: ignore
    users = await UserQuery.find_many_by_ids(user_ids)
    return await Format06.encode_users(users)
