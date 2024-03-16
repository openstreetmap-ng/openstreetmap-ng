from fastapi import APIRouter
from starlette import status
from starlette.responses import FileResponse, RedirectResponse

from app.lib.auth_context import auth_user
from app.lib.local_chapters import local_chapters
from app.lib.render_response import render_response

router = APIRouter()


@router.get('/')
@router.get('/export')
@router.get('/directions')
@router.get('/search')
@router.get('/query')
@router.get('/history')
@router.get('/history/nearby')
@router.get('/history/friends')
@router.get('/user/{_:str}/history')
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
    return render_response('communities.jinja2', {'local_chapters': local_chapters()})


@router.get('/copyright')
async def copyright():
    return render_response('copyright.jinja2')


@router.get('/help')
async def help():
    return render_response('help.jinja2')


@router.get('/about')
async def about():
    return render_response('about.jinja2')


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


@router.get('/robots.txt')
async def robots():
    return FileResponse('app/static/robots.txt', media_type='text/plain')
