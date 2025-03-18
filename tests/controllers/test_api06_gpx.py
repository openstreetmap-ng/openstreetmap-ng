from datetime import UTC, datetime
from math import isclose

import pytest
from httpx import AsyncClient
from starlette import status

from app.lib.xmltodict import XMLToDict


async def test_gpx_crud(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'

    original_filename = test_gpx_crud.__qualname__ + '.gpx'
    updated_filename = test_gpx_crud.__qualname__ + '_updated.gpx'
    file = XMLToDict.unparse(gpx, raw=True)

    # Create a new GPX trace
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'public',
            'description': 'Initial description',
            'tags': 'tag1,tag2',
        },
        files={
            'file': (original_filename, file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # Verify created trace
    r = await client.get(f'/api/0.6/gpx/{trace_id}/details')
    assert r.is_success, r.text
    gpx_file: dict = XMLToDict.parse(r.content)['osm']['gpx_file'][0]  # type: ignore

    assert gpx_file['@id'] == trace_id
    assert gpx_file['@user'] == 'user1'
    assert gpx_file['@name'] == original_filename
    assert gpx_file['@visibility'] == 'public'
    assert gpx_file['@pending'] is False
    assert gpx_file['description'] == 'Initial description'
    assert gpx_file['tag'] == ['tag1', 'tag2']

    created_at = gpx_file['@timestamp']

    # Update the trace
    r = await client.put(
        f'/api/0.6/gpx/{trace_id}',
        content=XMLToDict.unparse({
            'osm': {
                'gpx_file': {
                    '@name': updated_filename,
                    '@visibility': 'identifiable',
                    'description': 'Updated description',
                    'tag': ['updated_tag'],
                }
            }
        }),
    )
    assert r.is_success, r.text

    # Verify updated trace
    r = await client.get(f'/api/0.6/gpx/{trace_id}/details')
    assert r.is_success, r.text
    gpx_file = XMLToDict.parse(r.content)['osm']['gpx_file'][0]  # type: ignore

    assert gpx_file['@timestamp'] == created_at
    assert gpx_file['@name'] == updated_filename
    assert gpx_file['@visibility'] == 'identifiable'
    assert gpx_file['description'] == 'Updated description'
    assert gpx_file['tag'] == ['updated_tag']

    # Delete the trace
    r = await client.delete(f'/api/0.6/gpx/{trace_id}')
    assert r.is_success, r.text

    # Verify deletion
    r = await client.get(f'/api/0.6/gpx/{trace_id}/details')
    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_gpx_data_formats(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'

    file = XMLToDict.unparse(gpx, raw=True)

    # Create a new GPX trace
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'identifiable',
            'description': test_gpx_data_formats.__qualname__,
        },
        files={
            'file': (test_gpx_data_formats.__qualname__ + '.gpx', file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # Test raw data endpoint
    r = await client.get(f'/api/0.6/gpx/{trace_id}/data')
    assert r.is_success, r.text

    assert r.content == file
    assert r.headers['Content-Disposition'] == f'attachment; filename="{trace_id}"'

    # Test formatted GPX data endpoint
    r = await client.get(f'/api/0.6/gpx/{trace_id}/data.gpx')
    assert r.is_success, r.text

    assert r.content != file
    assert r.headers['Content-Disposition'] == f'attachment; filename="{trace_id}.gpx"'


async def test_gpx_files(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'

    file = XMLToDict.unparse(gpx, raw=True)

    # Create a new GPX trace
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'identifiable',
            'description': test_gpx_files.__qualname__,
        },
        files={
            'file': (test_gpx_files.__qualname__ + '.gpx', file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # List and verify traces
    r = await client.get('/api/0.6/user/gpx_files')
    assert r.is_success, r.text

    gpx_files: list[dict] = XMLToDict.parse(r.content)['osm']['gpx_file']  # type: ignore
    gpx_file = next(f for f in gpx_files if f['@id'] == trace_id)

    assert gpx_file['@user'] == 'user1'
    assert gpx_file['@name'] == test_gpx_files.__qualname__ + '.gpx'
    assert gpx_file['@visibility'] == 'identifiable'
    assert gpx_file['@pending'] is False
    assert gpx_file['description'] == test_gpx_files.__qualname__
    assert '@lon' in gpx_file
    assert '@lat' in gpx_file


@pytest.mark.parametrize(
    ('visibility', 'readable'),
    [
        ('private', False),
        ('public', True),
        ('identifiable', True),
        ('trackable', False),
    ],
)
async def test_gpx_visibility(client: AsyncClient, gpx: dict, visibility, readable):
    client.headers['Authorization'] = 'User user1'

    file = XMLToDict.unparse(gpx, raw=True)

    # Create trace with specified visibility
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': visibility,
            'description': f'{test_gpx_visibility.__qualname__}: {visibility}',
        },
        files={
            'file': (test_gpx_visibility.__qualname__ + '.gpx', file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # Verify created trace
    r = await client.get(f'/api/0.6/gpx/{trace_id}/details')
    assert r.is_success, r.text

    # Remove authorization header
    client.headers.pop('Authorization')

    # Verify unauthorized visibility
    r = await client.get(f'/api/0.6/gpx/{trace_id}/details')

    if readable:
        assert r.is_success, r.text
    else:
        assert r.status_code == status.HTTP_403_FORBIDDEN, r.text


async def test_trackpoints_visibility(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'

    file = XMLToDict.unparse(gpx, raw=True)

    # Create a new GPX trace
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'private',
            'description': test_trackpoints_visibility.__qualname__,
        },
        files={
            'file': (test_trackpoints_visibility.__qualname__ + '.gpx', file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # Query trackpoints
    r = await client.get(
        '/api/0.6/trackpoints',
        params={
            'bbox': '20.8726,51.8583,20.8728,51.8585',
        },
    )
    assert r.is_success, r.text

    trks: list[dict] = XMLToDict.parse(r.content)['gpx']['trk']  # type: ignore
    trk = next((t for t in trks if t.get('url') == f'/trace/{trace_id}'), None)
    assert trk is None, 'Trace must not be identified if private'

    # Update the trace to make it public
    r = await client.put(
        f'/api/0.6/gpx/{trace_id}',
        content=XMLToDict.unparse({
            'osm': {
                'gpx_file': {
                    '@name': test_trackpoints_visibility.__qualname__ + '.gpx',
                    '@visibility': 'public',
                    'description': test_trackpoints_visibility.__qualname__,
                },
            },
        }),
    )
    assert r.is_success, r.text

    # Query trackpoints again
    r = await client.get(
        '/api/0.6/trackpoints',
        params={
            'bbox': '20.8726,51.8583,20.8728,51.8585',
        },
    )
    assert r.is_success, r.text

    trks = XMLToDict.parse(r.content)['gpx']['trk']  # type: ignore
    trk = next(t for t in trks if t.get('url') == f'/trace/{trace_id}')
    assert trk['name'] == test_trackpoints_visibility.__qualname__ + '.gpx'
    assert trk['desc'] == test_trackpoints_visibility.__qualname__
    trkpt = trk['trkseg'][0]['trkpt'][0]
    assert trkpt['@lon'] == 20.8726996
    assert trkpt['@lat'] == 51.8583922
    assert datetime.fromisoformat(trkpt['time']) == datetime(2023, 7, 3, 10, 36, 21, tzinfo=UTC)
    assert isclose(trkpt['ele'], 190.8, abs_tol=0.01)
