from fastapi import APIRouter

from app.config import TEST_SITE_ACKNOWLEDGED_MAX_AGE
from app.lib.cookie import set_cookie
from app.lib.referrer import redirect_referrer

router = APIRouter(prefix='/api/web/test-site')


@router.post('/acknowledge')
async def acknowledge():
    response = redirect_referrer()
    set_cookie(
        response, 'test_site_acknowledged', '1', max_age=TEST_SITE_ACKNOWLEDGED_MAX_AGE
    )
    return response
