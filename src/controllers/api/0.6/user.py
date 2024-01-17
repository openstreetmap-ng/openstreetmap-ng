from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import PositiveInt

from src.lib.exceptions import raise_for
from src.lib.format.format06 import Format06
from src.lib_cython.auth import api_user
from src.models.db.user import User
from src.models.scope import Scope
from src.repositories.trace_repository import TraceRepository
from src.repositories.user_repository import UserRepository

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


@router.get('/user/{user_id}')
@router.get('/user/{user_id}.xml')
@router.get('/user/{user_id}.json')
async def user_read(
    user_id: PositiveInt,
) -> dict:
    user = await UserRepository.find_one_by_id(user_id)

    if user is None:
        raise_for().user_not_found(user_id)
    if False:  # TODO: if user deleted
        raise HTTPException(status.HTTP_410_GONE)

    return await Format06.encode_user(user)


@router.get('/users')
@router.get('/users.xml')
@router.get('/users.json')
async def users_read(
    users: Annotated[str, Query(min_length=1)],
) -> Sequence[dict]:
    query = (q.strip() for q in users.split(','))
    query = (q for q in query if q and q.isdigit())
    user_ids = {int(q) for q in query}

    if not user_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'No users were given to search for')

    users = await UserRepository.find_many_by_ids(user_ids)
    return await Format06.encode_users(users)
