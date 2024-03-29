from typing import Annotated

from fastapi import APIRouter
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import web_user
from app.lib.legal import legal_terms
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.user_status import UserStatus

router = APIRouter(prefix='/user')


@router.get('/terms')
async def terms(user: Annotated[User, web_user()]):
    if user.status != UserStatus.pending_terms:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return render_response(
        'user/terms.jinja2',
        {
            'legal_terms_GB': legal_terms('GB'),
            'legal_terms_FR': legal_terms('FR'),
            'legal_terms_IT': legal_terms('IT'),
        },
    )


@router.get('/account-confirm/pending')
async def account_confirm_pending(user: Annotated[User, web_user()]):
    if user.status != UserStatus.pending_activation:
        return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)
    return render_response('user/account_confirm_pending.jinja2')


@router.get('/new')
async def legacy_signup():
    return RedirectResponse('/signup', status.HTTP_301_MOVED_PERMANENTLY)
