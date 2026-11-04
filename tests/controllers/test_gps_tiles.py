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
from app.models.proto.trace_types import Visibility as TraceVisibility

_GPX_BYTES = Path('tests/data/8473730.gpx').read_bytes()


async def _upload_trace(
    client: AsyncClient,
    *,
    description: str,
    visibility: TraceVisibility,
) -> int:
    client.headers['Authorization'] = 'User user1'
    r = await client.post(
        '/rpc/trace.Service/Upload',
        headers={'Content-Type': 'application/proto'},
        content=UploadRequest(
            file=_GPX_BYTES,
            metadata=Metadata(
                name=f'{description}.gpx',
                description=description,
                tags=['gps-test'],
                visibility=Visibility.Value(visibility),
            ),
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    return int(UploadResponse.FromString(r.content).id)


async def test_gps_tile_server_renders_trace_lines(client: AsyncClient):
    await _upload_trace(
        client,
        description='test_gps_tile_public',
        visibility='public',
    )
    client.headers.pop('Authorization', None)

    # 1. Test standard .png URL
    r = await client.get('/gps/lines/14/9141/5422.png')
    assert r.status_code == 200, r.text
    assert r.headers['content-type'] == 'image/png'
    assert 'Cache-Control' in r.headers

    im = Image.open(BytesIO(r.content))
    assert im.size == (256, 256)
    assert im.mode == 'RGBA'
    # Check that at least one pixel is drawn (alpha > 0)
    alpha_extrema = im.getextrema()[3]
    assert alpha_extrema[1] > 0

    # 2. Test URL without .png suffix
    r2 = await client.get('/gps/lines/14/9141/5422')
    assert r2.status_code == 200
    assert r2.headers['content-type'] == 'image/png'
    assert r2.content == r.content


async def test_gps_tile_server_empty_tile(client: AsyncClient):
    # Tile in ocean / unpopulated area
    r = await client.get('/gps/lines/14/0/0.png')
    assert r.status_code == 200, r.text
    assert r.headers['content-type'] == 'image/png'

    im = Image.open(BytesIO(r.content))
    assert im.size == (256, 256)
    # Empty tile is fully transparent (all alpha == 0)
    alpha_extrema = im.getextrema()[3]
    assert alpha_extrema[1] == 0


async def test_gps_tile_server_out_of_bounds(client: AsyncClient):
    # For zoom 2, x cannot be 4 (max is 3)
    r = await client.get('/gps/lines/2/4/0.png')
    assert r.status_code == 404

    # Zoom > 20 is rejected by path validation (422)
    r = await client.get('/gps/lines/21/0/0.png')
    assert r.status_code == 422
