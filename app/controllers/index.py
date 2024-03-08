from fastapi import APIRouter
from starlette.responses import HTMLResponse

from app.lib.local_chapters import local_chapters
from app.lib.redirect_response import redirect_response
from app.lib.render_response import render_response
from app.services.auth_service import AuthService

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
async def index() -> HTMLResponse:
    return render_response('index.jinja2')


@router.get('/communities')
async def communities() -> HTMLResponse:
    return render_response('communities.jinja2', {'local_chapters': local_chapters()})


@router.get('/copyright')
async def copyright() -> HTMLResponse:
    return render_response('copyright.jinja2')


@router.get('/help')
async def help() -> HTMLResponse:
    return render_response('help.jinja2')


@router.get('/about')
async def about() -> HTMLResponse:
    return render_response('about.jinja2')


@router.get('/login')
async def login() -> HTMLResponse:
    return render_response('login.jinja2')


@router.get('/signup')
async def signup() -> HTMLResponse:
    return render_response('signup.jinja2')


@router.post('/logout')
async def logout():
    await AuthService.logout_session()
    return redirect_response()
