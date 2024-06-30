import pytest
from httpx import AsyncClient

from app.lib.xmltodict import XMLToDict

pytestmark = pytest.mark.anyio


async def test_gpx_crud(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'

    # create gpx
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'public',
            'description': 'before update',
            'tags': 'tag1,tag2',
        },
        files={
            'file': ('test_gpx_crud.gpx', XMLToDict.unparse(gpx, raw=True)),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # read trace
    r = await client.get(f'/api/0.6/gpx/{trace_id}/details')
    assert r.is_success, r.text
    gpx_file = XMLToDict.parse(r.content)['osm']['gpx_file'][0]

    assert gpx_file['@id'] == trace_id
    assert gpx_file['@user'] == 'user1'
    assert gpx_file['@name'] == 'test_gpx_crud.gpx'
    assert gpx_file['@visibility'] == 'public'
    assert gpx_file['@pending'] is False
    assert gpx_file['description'] == 'before update'
    assert gpx_file['tag'] == ['tag1', 'tag2']

    created_at = gpx_file['@timestamp']

    # update trace
    r = await client.put(
        f'/api/0.6/gpx/{trace_id}',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'gpx_file': {
                        '@name': 'test_gpx_crud_updated.gpx',
                        '@visibility': 'identifiable',
                        'description': 'after update',
                        'tag': ['test_gpx_crud'],
                    }
                }
            }
        ),
    )
    assert r.is_success, r.text

    # read trace
    r = await client.get(f'/api/0.6/gpx/{trace_id}/details')
    assert r.is_success, r.text
    gpx_file = XMLToDict.parse(r.content)['osm']['gpx_file'][0]

    assert gpx_file['@timestamp'] == created_at
    assert gpx_file['@name'] == 'test_gpx_crud_updated.gpx'
    assert gpx_file['@visibility'] == 'identifiable'
    assert gpx_file['description'] == 'after update'
    assert gpx_file['tag'] == ['test_gpx_crud']

    # delete trace
    r = await client.delete(f'/api/0.6/gpx/{trace_id}')
    assert r.is_success, r.text


async def test_gpx_data(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'
    file = XMLToDict.unparse(gpx, raw=True)

    # create gpx
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'identifiable',
            'description': 'test_gpx_data',
        },
        files={
            'file': ('test_gpx_data.gpx', file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # read trace raw data
    r = await client.get(f'/api/0.6/gpx/{trace_id}/data')
    assert r.is_success, r.text

    assert r.content == file
    assert r.headers['Content-Disposition'] == f'attachment; filename="{trace_id}"'
    assert 'Content-Type' not in r.headers

    # read trace gpx data
    r = await client.get(f'/api/0.6/gpx/{trace_id}/data.gpx')
    assert r.is_success, r.text

    assert r.content != file
    assert r.content.startswith(b'<?xml')
    assert r.headers['Content-Disposition'] == f'attachment; filename="{trace_id}.gpx"'
    assert r.headers['Content-Type'] == 'application/gpx+xml; charset=utf-8'


async def test_gpx_files(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'
    file = XMLToDict.unparse(gpx, raw=True)

    # create gpx
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'identifiable',
            'description': 'test_gpx_files',
        },
        files={
            'file': ('test_gpx_files.gpx', file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # read gpx files
    r = await client.get('/api/0.6/user/gpx_files')
    assert r.is_success, r.text

    gpx_files = XMLToDict.parse(r.content)['osm']['gpx_file']
    gpx_file = next(f for f in gpx_files if f['@id'] == trace_id)

    assert gpx_file['@user'] == 'user1'
    assert gpx_file['@name'] == 'test_gpx_files.gpx'
    assert gpx_file['@visibility'] == 'identifiable'
    assert gpx_file['@pending'] is False
    assert gpx_file['description'] == 'test_gpx_files'
    assert '@lon' in gpx_file
    assert '@lat' in gpx_file


async def test_trackpoints(client: AsyncClient, gpx: dict):
    client.headers['Authorization'] = 'User user1'
    file = XMLToDict.unparse(gpx, raw=True)

    # create gpx
    r = await client.post(
        '/api/0.6/gpx/create',
        data={
            'visibility': 'private',
            'description': 'test_trackpoints',
        },
        files={
            'file': ('test_trackpoints.gpx', file),
        },
    )
    assert r.is_success, r.text
    trace_id = int(r.text)

    # read trackpoints
    r = await client.get(
        '/api/0.6/trackpoints',
        params={
            'bbox': '20.8726,51.8583,20.8728,51.8585',
        },
    )
    assert r.is_success, r.text

    trks = XMLToDict.parse(r.content)['gpx']['trk']
    trk = next((t for t in trks if t.get('url') == f'/trace/{trace_id}'), None)
    assert trk is None

    # update trace
    r = await client.put(
        f'/api/0.6/gpx/{trace_id}',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'gpx_file': {
                        '@name': 'test_trackpoints.gpx',
                        '@visibility': 'identifiable',
                        'description': 'test_trackpoints',
                    }
                }
            }
        ),
    )
    assert r.is_success, r.text

    # read trackpoints
    r = await client.get(
        '/api/0.6/trackpoints',
        params={
            'bbox': '20.8726,51.8583,20.8728,51.8585',
        },
    )
    assert r.is_success, r.text

    trks = XMLToDict.parse(r.content)['gpx']['trk']
    trk = next(t for t in trks if t.get('url') == f'/trace/{trace_id}')
    assert trk['name'] == 'test_trackpoints.gpx'
    assert trk['desc'] == 'test_trackpoints'
    assert 'trkseg' in trk
