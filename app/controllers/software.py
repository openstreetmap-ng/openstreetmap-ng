from typing import Annotated

from fastapi import APIRouter, Query

from app.lib.render.response import render_response
from app.lib.software import FILTERS, filter_software, normalize_filters

router = APIRouter()


@router.get('/software')
async def software(
    category: Annotated[str, Query(max_length=32)] = '',
    platform: Annotated[str, Query(max_length=32)] = '',
    license: Annotated[str, Query(max_length=32)] = '',
    status: Annotated[str, Query(max_length=32)] = '',
):
    selected = normalize_filters({
        'category': category,
        'platform': platform,
        'license': license,
        'status': status,
    })
    return await render_response(
        'software/index',
        {
            'filters': FILTERS,
            'selected': selected,
            'entries': filter_software(selected),
        },
    )
