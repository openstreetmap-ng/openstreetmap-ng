from fastapi import APIRouter
from starlette.responses import RedirectResponse

from app.config import ENV, UNSUPPORTED_BROWSER_OVERRIDE_MAX_AGE
from app.lib.referrer import redirect_referrer

router = APIRouter(prefix='/api/web/unsupported-browser')


@router.post('/override')
async def override() -> RedirectResponse:
    response = redirect_referrer()
    response.set_cookie(
        key='unsupported_browser_override',
        value='1',
        max_age=int(UNSUPPORTED_BROWSER_OVERRIDE_MAX_AGE.total_seconds()),
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )
    return response
