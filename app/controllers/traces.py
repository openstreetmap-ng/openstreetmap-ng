from typing import Annotated

import cython
from fastapi import APIRouter, Path
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import auth_user, web_user
from app.lib.render_response import render_proto_page, render_response
from app.lib.translation import t
from app.models.db.user import User, user_proto
from app.models.proto.trace_pb2 import IndexPage
from app.models.types import TraceId
from app.queries.user_query import UserQuery
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/traces')
async def index():
    page = IndexPage()
    return await render_proto_page(
        page,
        title_prefix=_build_heading(page),
    )


@router.get('/traces/tag/{tag:str}')
async def tagged(
    tag: Annotated[str, Path(min_length=1)],
):
    page = IndexPage(tag=tag)
    return await render_proto_page(
        page,
        title_prefix=_build_heading(page),
    )


@router.get('/user/{display_name:str}/traces')
async def profile(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )

    current_user = auth_user()
    page = (
        IndexPage(self=IndexPage.Self())
        if current_user is not None and current_user['id'] == user['id']
        else IndexPage(profile=user_proto(user))
    )
    return await render_proto_page(
        page,
        title_prefix=_build_heading(page),
    )


@router.get('/user/{display_name:str}/traces/tag/{tag:str}')
async def profile_tagged(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
    tag: Annotated[str, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )

    current_user = auth_user()
    page = (
        IndexPage(tag=tag, self=IndexPage.Self())
        if current_user is not None and current_user['id'] == user['id']
        else IndexPage(
            profile=user_proto(user),
            tag=tag,
        )
    )
    return await render_proto_page(
        page,
        title_prefix=_build_heading(page),
    )


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


@cython.cfunc
def _build_heading(
    page: IndexPage,
):
    if page.HasField('self'):
        heading = t('traces.index.my_gps_traces')
    elif page.HasField('profile'):
        heading = t('traces.index.public_traces_from', user=page.profile.display_name)
    else:
        heading = t('traces.index.public_traces')

    return (
        f'{heading} {t("traces.index.tagged_with", tags=page.tag)}'
        if page.HasField('tag')
        else heading
    )
