from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

router = APIRouter(prefix='/unsupported-browser')


@router.post('/override')
async def override(request: Request) -> RedirectResponse:
    request.session['unsupported_browser_override'] = True
    return RedirectResponse(request.headers.get('Referer') or '/')
