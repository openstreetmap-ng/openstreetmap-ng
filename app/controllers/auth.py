from fastapi import APIRouter

from app.lib.referrer import get_redirect_response
from app.services.auth_service import AuthService

router = APIRouter()


@router.post('/logout')
async def logout():
    await AuthService.logout_session()
    return get_redirect_response()
