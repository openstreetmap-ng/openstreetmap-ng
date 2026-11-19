from io import BytesIO

import pytest
from httpx import AsyncClient
from PIL import Image

from app.db import db, db_delete
from app.lib.geo.gps_tile import gps_tile_bounds
from app.queries.gps_tile_query import GPSTileQuery


async def _upload(
    client: AsyncClient, visibility: str, segments: list[list[tuple[float, float]]]
):
    tracks = ''.join(
        '<trkseg>'
        + ''.join(f'<trkpt lon="{lon}" lat="{lat}"/>' for lon, lat in segment)
        + '</trkseg>'
        for segment in segments
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gpx version="1.1" creator="tests"><trk>{tracks}</trk></gpx>'
    ).encode()
    client.headers['Authorization'] = 'User user1'
    response = await client.post(
        '/api/0.6/gpx/create',
        data={'visibility': visibility, 'description': 'GPS tile regression'},
        files={'file': ('tile.gpx', content)},
    )
    assert response.is_success, response.text
    return int(response.text)


@pytest.fixture
async def empty_traces():
    # Other GPX controller tests leave traces behind; isolate spatial assertions.
    async with db(True) as conn:
        await db_delete('trace', where=t'TRUE', conn=conn)


@pytest.mark.parametrize('suffix', ['', '.png'])
async def test_empty_tile(client: AsyncClient, empty_traces, suffix: str):
    response = await client.get(f'/gps/lines/0/0/0{suffix}')
    assert response.is_success, response.text
    assert response.headers['content-type'] == 'image/png'
    assert 'max-age=60' in response.headers['cache-control']
    image = Image.open(BytesIO(response.content))
    assert image.size == (256, 256)
    assert image.getchannel('A').getbbox() is None


@pytest.mark.parametrize('tile', ['21/0/0', '3/8/0', '3/0/8', '-1/0/0', '3/-1/0'])
async def test_invalid_tile(client: AsyncClient, tile: str):
    assert (await client.get(f'/gps/lines/{tile}.png')).status_code == 404


@pytest.mark.parametrize(
    'visibility', ['public', 'identifiable', 'private', 'trackable']
)
async def test_crossing_and_visibility(
    client: AsyncClient, empty_traces, visibility: str
):
    # z=3 x=4 spans [0,45]; neither endpoint lies inside it.
    await _upload(client, visibility, [[(-5, 20), (50, 20)]])
    for authenticated in (True, False):
        if not authenticated:
            client.headers.pop('Authorization', None)
        response = await client.get('/gps/lines/3/4/3.png')
        assert response.is_success, response.text
        image = Image.open(BytesIO(response.content))
        painted = image.getchannel('A').getbbox() is not None
        assert painted == (visibility in {'public', 'identifiable'})
        if painted:
            # Both tile boundaries are crossed, not just a single sampled point.
            assert image.getchannel('A').crop((0, 0, 1, 256)).getbbox()
            assert image.getchannel('A').crop((255, 0, 256, 256)).getbbox()


async def test_date_line_does_not_cross_greenwich(client: AsyncClient, empty_traces):
    await _upload(client, 'public', [[(179, 20), (-179, 20)]])
    assert not await GPSTileQuery.find_lines(gps_tile_bounds(3, 4, 3))
    for x in (0, 7):
        response = await client.get(f'/gps/lines/3/{x}/3.png')
        assert response.is_success, response.text
        assert Image.open(BytesIO(response.content)).getchannel('A').getbbox()


async def test_separate_segments_are_not_joined(client: AsyncClient, empty_traces):
    await _upload(client, 'public', [[(5, 10), (6, 10)], [(35, 30), (36, 30)]])
    lines = await GPSTileQuery.find_lines(gps_tile_bounds(3, 4, 3))
    assert len(lines) == 2
    assert all(line.length < 2 for line in lines)
