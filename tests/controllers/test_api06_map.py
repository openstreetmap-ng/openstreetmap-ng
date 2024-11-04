from collections.abc import Sequence

import pytest
from httpx import AsyncClient

from app.lib.xmltodict import XMLToDict
from app.models.element import ElementType


async def test_map_read(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'changeset': {
                        'tag': [
                            {'@k': 'created_by', '@v': test_map_read.__name__},
                        ]
                    }
                }
            }
        ),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # create node
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'node': {
                        '@changeset': changeset_id,
                        '@lon': 1.2345678111111,
                        '@lat': 2.3456789111111,
                        'tag': [
                            {'@k': 'created_by', '@v': test_map_read.__name__},
                        ],
                    }
                }
            }
        ),
    )
    assert r.is_success, r.text
    node_id = int(r.text)

    # read map
    r = await client.get('/api/0.6/map?bbox=1.234,2.345,1.235,2.346')
    assert r.is_success, r.text

    data: Sequence[tuple[ElementType, dict]] = XMLToDict.parse(r.content)['osm']
    nodes = (value for key, value in data if key == 'node')
    node = next(node for node in nodes if node['@id'] == node_id)
    assert node['@lon'] == 1.2345678
    assert node['@lat'] == 2.3456789

    # delete node
    r = await client.request(
        'DELETE',
        f'/api/0.6/node/{node_id}',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'node': {
                        '@changeset': changeset_id,
                        '@version': 1,
                    }
                }
            }
        ),
    )
    assert r.is_success, r.text
    version = int(r.text)

    assert version == 2

    # read map
    r = await client.get('/api/0.6/map?bbox=1.234,2.345,1.235,2.346')
    assert r.is_success, r.text

    data = XMLToDict.parse(r.content)['osm']

    # empty map will be parsed as dict
    if isinstance(data, Sequence):  # pyright: ignore[reportUnnecessaryIsInstance]
        nodes = (value for key, value in data if key == 'node')
        with pytest.raises(StopIteration):
            node = next(node for node in nodes if node['@id'] == node_id)
