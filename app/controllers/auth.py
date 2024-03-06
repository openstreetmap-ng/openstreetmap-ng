from fastapi import APIRouter
from starlette import status
from starlette.responses import HTMLResponse, RedirectResponse

from app.lib.redirect_response import redirect_response
from app.lib.render_response import render_response
from app.services.auth_service import AuthService

router = APIRouter()


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


@router.get('/user/new')
async def legacy_signup():
    return RedirectResponse('/signup', status.HTTP_301_MOVED_PERMANENTLY)
