from typing import Annotated

import magic
from fastapi import APIRouter, Path, Response

from app.models.types import StorageKey
from app.queries.background_query import BackgroundQuery

router = APIRouter(prefix='/api/web/background')


@router.get('/custom/{background_id}')
async def custom(
    background_id: Annotated[StorageKey, Path(min_length=1)],
) -> Response:
    file = await BackgroundQuery.get_custom(background_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)
