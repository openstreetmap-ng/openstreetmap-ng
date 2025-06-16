from typing import Annotated

from fastapi import APIRouter, Query

from app.config import ENV
from app.lib.render_response import render_response

router = APIRouter()

if ENV != 'prod':

    @router.get('/test')
    async def test_site(referer: Annotated[str | None, Query()] = None):
        return await render_response('test-site', {'referer': referer or '/'})
