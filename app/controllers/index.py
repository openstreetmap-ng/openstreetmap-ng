from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, status
from feedgen.feed import FeedGenerator
from pydantic import PositiveInt
from starlette import status
from starlette.responses import FileResponse, RedirectResponse

from app.config import APP_URL
from app.controllers.api06_changeset import query_changesets
from app.format import FormatRSS06
from app.lib.auth_context import auth_user, web_user
from app.lib.local_chapters import LOCAL_CHAPTERS
from app.lib.render_response import render_response
from app.lib.translation import t
from app.limits import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from app.models.db.user import User

router = APIRouter()


@router.get('/robots.txt')
async def robots():
    return FileResponse('app/static/robots.txt', media_type='text/plain')


@router.get('/')
@router.get('/export')
@router.get('/directions')
@router.get('/search')
@router.get('/query')
@router.get('/history')
@router.get('/history/nearby')
@router.get('/history/friends')
@router.get('/user/{_:str}/history')
@router.get('/note/new')
@router.get('/note/{_:int}')
@router.get('/changeset/{_:int}')
@router.get('/node/{_:int}')
@router.get('/node/{_:int}/history')
@router.get('/node/{_:int}/history/{__:int}')
@router.get('/way/{_:int}')
@router.get('/way/{_:int}/history')
@router.get('/way/{_:int}/history/{__:int}')
@router.get('/relation/{_:int}')
@router.get('/relation/{_:int}/history')
@router.get('/relation/{_:int}/history/{__:int}')
async def index():
    return render_response('index.jinja2')


@router.get('/communities')
async def communities():
    return render_response('communities.jinja2', {'local_chapters': LOCAL_CHAPTERS})


@router.get('/copyright')
async def copyright_():
    return render_response('copyright.jinja2')


@router.get('/help')
async def help_():
    return render_response('help.jinja2')


@router.get('/about')
async def about():
    return render_response('about.jinja2')


@router.get('/fixthemap')
async def fixthemap():
    return render_response('fixthemap.jinja2')


@router.get('/login')
async def login():
    if auth_user() is not None:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return render_response('user/login.jinja2')


@router.get('/signup')
async def signup():
    if auth_user() is not None:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return render_response('user/signup.jinja2')


@router.get('/welcome')
async def welcome(_: Annotated[User, web_user()]):
    return render_response('welcome.jinja2')


@router.get('/settings')
async def settings(_: Annotated[User, web_user()]):
    return render_response('user/settings/index.jinja2')


@router.get('/history/feed')
async def history_feed(
    request: Request,
    changeset_ids_str: Annotated[str | None, Query(alias='changesets', min_length=1)] = None,
    display_name: Annotated[str | None, Query(min_length=1)] = None,
    user_id: Annotated[PositiveInt | None, Query(alias='user')] = None,
    time: Annotated[str | None, Query(min_length=1)] = None,
    open_str: Annotated[str | None, Query(alias='open')] = None,
    closed_str: Annotated[str | None, Query(alias='closed')] = None,
    bbox: Annotated[str | None, Query(min_length=1)] = None,
    order: Annotated[Literal['newest', 'oldest'], Query()] = 'newest',
    limit: Annotated[int, Query(gt=0, le=CHANGESET_QUERY_MAX_LIMIT)] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    changesets = await query_changesets(
        changeset_ids_str, display_name, user_id, time, open_str, closed_str, bbox, order, limit
    )
    fg = FeedGenerator()
    fg.link(href=str(request.url), rel='self')
    fg.title(t('changesets.index.title'))
    fg.id(f'{APP_URL}/history/feed')
    fg.updated(utcnow())
    fg.generator('')
    await FormatRSS06.encode_changesets(fg, changesets)
    return fg.atom_str()
