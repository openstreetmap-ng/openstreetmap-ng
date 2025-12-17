from typing import Annotated

import cython
from fastapi import APIRouter, Path
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import auth_user, web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.types import TraceId
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/traces')
async def index():
    data = await _get_data(user=None, tag=None)
    return await render_response('traces/index', data)


@router.get('/traces/tag/{tag:str}')
async def tagged(
    tag: Annotated[str, Path(min_length=1)],
):
    data = await _get_data(user=None, tag=tag)
    return await render_response('traces/index', data)


@router.get('/user/{display_name:str}/traces')
async def personal(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    data = await _get_data(user=user, tag=None)
    return await render_response('traces/index', data)


@router.get('/user/{display_name:str}/traces/tag/{tag:str}')
async def personal_tagged(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
    tag: Annotated[str, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    data = await _get_data(user=user, tag=tag)
    return await render_response('traces/index', data)


@router.get('/user/{_:str}/traces/{trace_id:int}')
async def legacy_personal_details(_, trace_id: TraceId):
    return RedirectResponse(f'/trace/{trace_id}', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/traces/mine{suffix:path}')
async def legacy_mine(
    user: Annotated[User, web_user()],
    suffix: str,
):
    return RedirectResponse(
        f'/user/{user["display_name"]}/traces{suffix}',
        status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get('/traces/new')
async def legacy_new():
    return RedirectResponse('/trace/upload', status.HTTP_301_MOVED_PERMANENTLY)


async def _get_data(
    *,
    user: User | None,
    tag: str | None,
) -> dict:
    base_url = f'/user/{user["display_name"]}/traces' if user is not None else '/traces'
    base_url_notag = base_url
    if tag is not None:
        base_url += f'/tag/{tag}'

    active_tab = _get_active_tab(user)

    pagination_action = '/api/web/traces/page'
    query_params = []
    if user is not None:
        query_params.append(f'user_id={user["id"]}')
    if tag is not None:
        query_params.append(f'tag={tag}')
    if query_params:
        pagination_action += '?' + '&'.join(query_params)

    return {
        'profile': user,
        'active_tab': active_tab,
        'base_url': base_url,
        'base_url_notag': base_url_notag,
        'tag': tag,
        'pagination_action': pagination_action,
    }


@cython.cfunc
def _get_active_tab(user: User | None) -> int:
    """Get the active tab number for the traces page."""
    if user is not None:
        current_user = auth_user()
        if current_user is not None and user['id'] == current_user['id']:
            return 1  # viewing own traces
        return 2  # viewing other user's traces

    return 0  # viewing public traces
