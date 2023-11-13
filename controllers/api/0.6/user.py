from typing import Annotated, Sequence

from fastapi import APIRouter, HTTPException, Query, status

from lib.auth import api_user
from lib.format.format06 import Format06
from models.db.base_sequential import SequentialId
from models.db.trace_ import Trace
from models.db.user import User
from models.scope import Scope
from models.str import NonEmptyStr

router = APIRouter()


@router.get('/user/gpx_files')
@router.get('/user/gpx_files.xml')
async def user_gpx_files(user: Annotated[User, api_user(Scope.read_gpx)]) -> Sequence[dict]:
    traces = await Trace.find_many_by_user_id(user.id)
    return Format06.encode_gpx_files(traces)


@router.get('/user/details')
@router.get('/user/details.xml')
@router.get('/user/details.json')
async def user_details(user: Annotated[User, api_user()]) -> dict:
    return Format06.encode_user(user)


@router.get('/user/{user_id}')
@router.get('/user/{user_id}.xml')
@router.get('/user/{user_id}.json')
async def user_read(user_id: SequentialId) -> dict:
    user = await User.find_one_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # TODO: if user deleted
    if False:
        raise HTTPException(status.HTTP_410_GONE)
    return Format06.encode_user(user)


@router.get('/users')
@router.get('/users.xml')
@router.get('/users.json')
async def users_read(users: Annotated[NonEmptyStr, Query()]) -> Sequence[dict]:
    query = (q.strip() for q in users.split(','))
    query = (q for q in query if q and q.isdigit())
    user_ids = set(int(q) for q in query)
    users = await User.find_many_by_ids(user_ids)
    return Format06.encode_users(users)
