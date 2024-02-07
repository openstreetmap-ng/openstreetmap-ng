from fastapi import APIRouter
from starlette.responses import HTMLResponse

from app.lib.render_response import render_response

router = APIRouter()


@router.get('/')
async def index() -> HTMLResponse:
    return render_response('index.jinja2')
