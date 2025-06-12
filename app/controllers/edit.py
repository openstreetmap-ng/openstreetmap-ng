from typing import Annotated

from fastapi import APIRouter

from app.config import ID_URL, RAPID_URL
from app.lib.auth_context import auth_user, web_user
from app.lib.bun_packages import ID_VERSION, RAPID_VERSION
from app.lib.render_response import render_response
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
    return await render_response('edit/id-iframe', {'ID_VERSION': ID_VERSION})


@router.get('/rapid')
async def rapid():
    return await render_response('edit/rapid-iframe', {'RAPID_VERSION': RAPID_VERSION})
