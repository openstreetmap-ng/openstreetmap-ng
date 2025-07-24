from typing import Annotated

from fastapi import APIRouter

from app.config import ID_URL, RAPID_URL
from app.lib.auth_context import auth_user, web_user
from app.lib.render_response import render_response
from app.middlewares.default_headers_middleware import CSP_HEADER
from app.models.db.user import DEFAULT_EDITOR, Editor, User

router = APIRouter()


@router.get('/edit')
async def edit(
    _: Annotated[User, web_user()],
    editor: Editor | None = None,
):
    if editor is None:
        current_user = auth_user()
        if current_user is not None:
            editor = current_user['editor']
        if editor is None:
            editor = DEFAULT_EDITOR

    if editor == 'id':
        return await render_response('edit/id', {'ID_URL': ID_URL})
    if editor == 'rapid':
        return await render_response('edit/rapid', {'RAPID_URL': RAPID_URL})
    if editor == 'remote':
        return await render_response('index/index')

    raise NotImplementedError(f'Unsupported editor {editor!r}')


@router.get('/id')
async def id():
    return await render_response('edit/id-iframe')


# Rapid requires unsafe-eval
# https://github.com/facebook/Rapid/issues/1718
_RAPID_CSP_HEADER = CSP_HEADER.replace('script-src', "script-src 'unsafe-eval'", 1)


@router.get('/rapid')
async def rapid():
    response = await render_response('edit/rapid-iframe')
    response.headers['Content-Security-Policy'] = _RAPID_CSP_HEADER
    return response
