from fastapi import APIRouter

from app.config import ENV, TEST_SITE_ACKNOWLEDGED_MAX_AGE
from app.lib.referrer import redirect_referrer

router = APIRouter(prefix='/api/web/test-site')


@router.post('/acknowledge')
async def acknowledge():
    response = redirect_referrer()
    response.set_cookie(
        key='test_site_acknowledged',
        value='1',
        max_age=int(TEST_SITE_ACKNOWLEDGED_MAX_AGE.total_seconds()),
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )
    return response
