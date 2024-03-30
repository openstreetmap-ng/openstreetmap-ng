from typing import Annotated

from fastapi import APIRouter

from app.lib.auth_context import auth_user, web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.editor import DEFAULT_EDITOR, Editor

router = APIRouter()


@router.get('/edit')
async def edit(
    _: Annotated[User, web_user()],
    editor: Editor | None = None,
):
    if editor is None:
        current_user = auth_user()
        if current_user is not None:
            editor = current_user.editor
        if editor is None:
            editor = DEFAULT_EDITOR

    if editor == Editor.id:
        return render_response('edit/id.jinja2')
    elif editor == Editor.rapid:
        return render_response('edit/rapid.jinja2')
    elif editor == Editor.remote:
        return render_response('index.jinja2')
    else:
        raise NotImplementedError(f'Unsupported editor {editor!r}')


@router.get('/id')
async def id(_: Annotated[User, web_user()]):
    return render_response('edit/id_iframe.jinja2')


@router.get('/rapid')
async def rapid(_: Annotated[User, web_user()]):
    return render_response('edit/rapid_iframe.jinja2')
