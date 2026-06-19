from io import BytesIO
from pathlib import Path

from httpx import AsyncClient
from PIL import Image

from app.models.proto.trace_pb2 import (
    Metadata,
    UploadRequest,
    UploadResponse,
    Visibility,
)

_GPX_BYTES = Path('tests/data/8473730.gpx').read_bytes()
_TRACE_TILE = '/gps/lines/14/9141/5422.png'
_TRACE_TILE_DEFAULT_FORMAT = '/gps/lines/14/9141/5422'
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


async def _upload_trace(client: AsyncClient, visibility: int):
    r = await client.post(
        '/rpc/trace.Service/Upload',
        headers={'Content-Type': 'application/proto'},
        content=UploadRequest(
            file=_GPX_BYTES,
            metadata=Metadata(
                name='trace-tile-test.gpx',
                description='Trace tile test',
                tags=['trace-tile-test'],
                visibility=visibility,
            ),
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    return int(UploadResponse.FromString(r.content).id)


def _has_visible_pixel(content: bytes):
    image = Image.open(BytesIO(content)).convert('RGBA')
    return image.getchannel('A').getbbox() is not None


async def test_public_trace_tile(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    await _upload_trace(client, Visibility.private)
    client.headers.pop('Authorization')

    r = await client.get(_TRACE_TILE)

    assert r.is_success, r.text
    assert r.headers['Content-Type'] == 'image/png'
    assert r.content.startswith(_PNG_SIGNATURE)
    assert _has_visible_pixel(r.content)

    r_default = await client.get(_TRACE_TILE_DEFAULT_FORMAT)
    assert r_default.is_success, r_default.text
    assert r_default.content == r.content
