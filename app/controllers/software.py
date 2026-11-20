from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.lib.render.response import render_response
from app.lib.software_directory import (
    CATEGORIES,
    LICENSES,
    MAINTENANCE,
    PLATFORMS,
    filter_software,
)

router = APIRouter()


@router.get('/software')
async def software(
    category: Literal['', 'editing', 'navigation', 'cartography'] = '',
    platform: Literal['', 'web', 'windows', 'macos', 'linux', 'android', 'ios'] = '',
    license_filter: Annotated[
        Literal['', 'open', 'proprietary'], Query(alias='license')
    ] = '',
    maintenance: Literal['', 'active', 'inactive'] = '',
):
    return await render_response(
        'software',
        {
            'software': filter_software(
                category=category,
                platform=platform,
                license_type=license_filter,
                maintenance=maintenance,
            ),
            'filters': {
                'category': category,
                'platform': platform,
                'license': license_filter,
                'maintenance': maintenance,
            },
            'options': {
                'category': CATEGORIES,
                'platform': PLATFORMS,
                'license': LICENSES,
                'maintenance': MAINTENANCE,
            },
        },
    )
