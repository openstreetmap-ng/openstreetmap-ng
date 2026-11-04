from typing import Annotated

from fastapi import APIRouter, Query

from app.lib.render.response import render_response
from app.lib.software import FILTERS, filter_software

router = APIRouter()


@router.get('/software')
async def software(
    category: Annotated[str, Query(max_length=32)] = '',
    platform: Annotated[str, Query(max_length=32)] = '',
    license: Annotated[str, Query(max_length=32)] = '',
    status: Annotated[str, Query(max_length=32)] = '',
):
    selected = {
        'category': category,
        'platform': platform,
        'license': license,
        'status': status,
    }
    # Unknown values normalize to All, keeping the displayed form and results consistent.
    selected = {
        key: value if value in FILTERS[key] else '' for key, value in selected.items()
    }
    return await render_response(
        'software',
        {
            'entries': filter_software(selected),
            'filters': FILTERS,
            'selected': selected,
        },
    )
