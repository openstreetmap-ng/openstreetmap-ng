from io import BytesIO

import pytest
from httpx import AsyncClient
from PIL import Image

from app.db import db_fetchval
from app.lib.geo.gps_tiles import GPS_MASTER_ZOOM


@pytest.mark.parametrize('suffix', ['', '.png'])
async def test_gps_png_suffix(client: AsyncClient, suffix: str):
    response = await client.get(f'/gps/lines/0/0/0{suffix}')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/png'
    image = Image.open(BytesIO(response.content))
    assert image.size == (256, 256)
    assert image.mode == 'RGBA'


@pytest.mark.parametrize('path', ['-1/0/0', '17/0/0', '0/1/0', '0/0/1'])
async def test_gps_invalid_coordinates(client: AsyncClient, path: str):
    assert (await client.get(f'/gps/lines/{path}.png')).status_code == 400


async def test_uploaded_trace_contributes_and_is_removed(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    content = b'<gpx version="1.1"><trk><trkseg><trkpt lat="0" lon="0"/><trkpt lat="0" lon="0.001"/></trkseg></trk></gpx>'
    ids = []
    try:
        for _ in range(2):
            response = await client.post(
                '/api/0.6/gpx/create',
                data={
                    'visibility': 'public',
                    'description': 'Synthetic GPS tile regression',
                },
                files={'file': ('gps-tiles.gpx', content)},
            )
            assert response.is_success, response.text
            ids.append(int(response.text))
        trace_id = ids[0]
        assert (
            await db_fetchval(
                int, t'SELECT count(*) FROM gps_trace_index WHERE trace_id = {trace_id}'
            )
            == 1
        )
        assert (
            await db_fetchval(
                int, t'SELECT count(*) FROM gps_trace_pixel WHERE trace_id = {trace_id}'
            )
            > 0
        )
        tile = await client.get(f'/gps/lines/{GPS_MASTER_ZOOM}/32768/32768.png')
        assert tile.status_code == 200
        assert Image.open(BytesIO(tile.content)).getchannel('A').getbbox() is not None
        response = await client.delete(f'/api/0.6/gpx/{trace_id}')
        assert response.is_success, response.text
        ids.remove(trace_id)
        assert (
            await db_fetchval(
                int, t'SELECT count(*) FROM gps_trace_pixel WHERE trace_id = {trace_id}'
            )
            == 0
        )
        tile = await client.get(f'/gps/lines/{GPS_MASTER_ZOOM}/32768/32768.png')
        assert Image.open(BytesIO(tile.content)).getchannel('A').getbbox() is not None
    finally:
        for trace_id in ids:
            response = await client.delete(f'/api/0.6/gpx/{trace_id}')
            assert response.is_success, response.text
