from fastapi import APIRouter, Request
from starlette import status
from starlette.responses import RedirectResponse

from app.config import COOKIE_GENERIC_MAX_AGE, ENV

router = APIRouter(prefix='/api/web/unsupported-browser')


@router.post('/override')
async def override(request: Request) -> RedirectResponse:
    response = RedirectResponse(request.headers.get('Referer') or '/', status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key='unsupported_browser_override',
        value='1',
        max_age=int(COOKIE_GENERIC_MAX_AGE.total_seconds()),
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )
    return response
