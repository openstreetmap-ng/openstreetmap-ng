from fastapi import APIRouter, Request
from starlette import status
from starlette.responses import RedirectResponse

from app.config import TEST_ENV
from app.limits import COOKIE_GENERIC_MAX_AGE

router = APIRouter(prefix='/unsupported-browser')


@router.post('/override')
async def override(request: Request) -> RedirectResponse:
    response = RedirectResponse(request.headers.get('Referer') or '/', status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        'unsupported_browser_override',
        '1',
        COOKIE_GENERIC_MAX_AGE,
        secure=not TEST_ENV,
        httponly=True,
        samesite='lax',
    )
    return response
