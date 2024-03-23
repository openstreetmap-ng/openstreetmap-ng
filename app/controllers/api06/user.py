from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from pydantic import PositiveInt

from app.format06 import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.models.db.user import User
from app.models.scope import Scope
from app.repositories.trace_repository import TraceRepository
from app.repositories.user_repository import UserRepository

router = APIRouter()


@router.get('/user/gpx_files')
@router.get('/user/gpx_files.xml')
async def user_gpx_files(
    user: Annotated[User, api_user(Scope.read_gpx)],
) -> Sequence[dict]:
    traces = await TraceRepository.find_many_by_user_id(user.id, limit=None)
    return Format06.encode_gpx_files(traces)


@router.get('/user/details')
@router.get('/user/details.xml')
@router.get('/user/details.json')
async def user_details(
    user: Annotated[User, api_user()],
) -> dict:
    return await Format06.encode_user(user)


@router.get('/user/{user_id:int}')
@router.get('/user/{user_id:int}.xml')
@router.get('/user/{user_id:int}.json')
async def user_read(
    user_id: PositiveInt,
) -> dict:
    user = await UserRepository.find_one_by_id(user_id)

    if user is None:
        raise_for().user_not_found(user_id)
    if False:  # TODO: if user deleted
        return Response(None, status.HTTP_410_GONE)

    return await Format06.encode_user(user)


@router.get('/users')
@router.get('/users.xml')
@router.get('/users.json')
async def users_read(
    users: Annotated[str, Query(min_length=1)],
) -> Sequence[dict]:
    user_ids = set()

    for q in users.split(','):
        q = q.strip()
        if q.isdigit():
            user_ids.add(int(q))

    if not user_ids:
        return Response('No users were given to search for', status.HTTP_400_BAD_REQUEST)

    users = await UserRepository.find_many_by_ids(user_ids)
    return await Format06.encode_users(users)
