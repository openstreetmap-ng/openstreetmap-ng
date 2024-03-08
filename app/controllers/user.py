from fastapi import APIRouter
from starlette import status
from starlette.responses import HTMLResponse, RedirectResponse

from app.lib.legal import get_legal_terms
from app.lib.render_response import render_response

router = APIRouter(prefix='/user')


@router.get('/terms')
async def terms() -> HTMLResponse:
    return render_response(
        'user/terms.jinja2',
        {
            'legal_terms_GB': get_legal_terms('GB'),
            'legal_terms_FR': get_legal_terms('FR'),
            'legal_terms_IT': get_legal_terms('IT'),
        },
    )


@router.get('/new')
async def legacy_signup():
    return RedirectResponse('/signup', status.HTTP_301_MOVED_PERMANENTLY)
