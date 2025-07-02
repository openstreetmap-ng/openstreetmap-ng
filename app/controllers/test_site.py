from typing import Annotated

from fastapi import APIRouter, Query
from starlette import status

from app.config import ENV
from app.lib.render_response import render_response

router = APIRouter()

if ENV != 'prod':

    @router.get('/test-site')
    async def test_site(referer: Annotated[str | None, Query()] = None):  # noqa: PT028
        return await render_response(
            'test-site',
            {'referer': referer or '/'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
