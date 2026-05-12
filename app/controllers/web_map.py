import base64
import hmac
import time
from hashlib import sha1
from typing import Annotated, Literal
from urllib.parse import urlencode

from app.config import RENDER_EXPORT_TOTP_KEY, RENDER_EXPORT_URL
from app.lib.geo_utils import parse_bbox
from fastapi import APIRouter, Query
from pydantic import PositiveInt
from starlette import status
from starlette.responses import RedirectResponse

router = APIRouter(prefix='/api/web/map')


@router.get('/export')
async def export_map(
    bbox: Annotated[str, Query(min_length=1)],
    scale: Annotated[PositiveInt, Query()],
    format: Annotated[Literal['svg', 'pdf'], Query()],
):
    bounds = parse_bbox(bbox).bounds
    params = {
        'bbox': ','.join(str(v) for v in bounds),
        'scale': str(scale),
        'format': format,
        'token': _render_export_totp(),
    }
    return RedirectResponse(
        f'{RENDER_EXPORT_URL}?{urlencode(params)}',
        status.HTTP_303_SEE_OTHER,
    )


def _render_export_totp():
    secret = RENDER_EXPORT_TOTP_KEY.get_secret_value()
    if not secret:
        return ''

    normalized = secret.replace(' ', '').upper()
    normalized += '=' * (-len(normalized) % 8)
    key = base64.b32decode(normalized)
    counter = int(time.time() // 3600)
    digest = hmac.new(key, counter.to_bytes(8, 'big'), sha1).digest()
    offset = digest[-1] & 0x0F
    code = int.from_bytes(digest[offset : offset + 4], 'big') & 0x7FFFFFFF
    return f'{code % 1_000_000:06d}'
