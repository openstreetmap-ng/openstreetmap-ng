from fastapi import APIRouter

from app.config import UNSUPPORTED_BROWSER_OVERRIDE_MAX_AGE
from app.lib.cookie import set_cookie
from app.lib.referrer import redirect_referrer

router = APIRouter(prefix='/api/web/unsupported-browser')


@router.post('/override')
async def override():
    response = redirect_referrer()
    set_cookie(
        response,
        'unsupported_browser_override',
        '1',
        max_age=UNSUPPORTED_BROWSER_OVERRIDE_MAX_AGE,
    )
    return response
