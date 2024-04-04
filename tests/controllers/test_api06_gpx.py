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
    gpx_file = XMLToDict.parse(r.content)['osm']['gpx_file']

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
    gpx_file = XMLToDict.parse(r.content)['osm']['gpx_file']

    assert gpx_file['@id'] == trace_id
    assert gpx_file['@user'] == 'user1'
    assert gpx_file['@name'] == 'test_gpx_crud_updated.gpx'
    assert gpx_file['@visibility'] == 'identifiable'
    assert gpx_file['@pending'] is False
    assert gpx_file['description'] == 'after update'
    assert gpx_file['tag'] == ['test_gpx_crud']
    assert gpx_file['@timestamp'] == created_at

    # delete trace
    r = await client.delete(f'/api/0.6/gpx/{trace_id}')
    assert r.is_success, r.text
