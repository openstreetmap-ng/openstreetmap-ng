import random

from httpx import AsyncClient

from app.config import GEO_COORDINATE_PRECISION
from app.lib.xmltodict import XMLToDict
from tests.utils.assert_model import assert_model


async def test_map_read(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': test_map_read.__name__}]}}
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Create a node at random coordinates
    lon = round(random.uniform(-179, 179), GEO_COORDINATE_PRECISION)
    lat = round(random.uniform(-89, 89), GEO_COORDINATE_PRECISION)
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': lon,
                    '@lat': lat,
                    'tag': [{'@k': 'created_by', '@v': test_map_read.__name__}],
                }
            }
        }),
    )
    assert r.is_success, r.text
    node_id = int(r.text)

    # Retrieve the node
    bbox = f'{lon},{lat},{lon},{lat}'
    r = await client.get('/api/0.6/map', params={'bbox': bbox})
    assert r.is_success, r.text

    map_data = XMLToDict.parse(r.content)['osm']
    assert isinstance(map_data, list), 'Map response must contain elements'

    # Find our node in the response
    nodes = [value for key, value in map_data if key == 'node']
    target_node = next((node for node in nodes if node['@id'] == node_id), None)
    assert target_node is not None, 'Created node must be found in map response'
    assert_model(
        target_node,
        {
            '@id': node_id,
            '@lon': lon,
            '@lat': lat,
            '@changeset': changeset_id,
            '@version': 1,
            '@visible': True,
        },
    )

    # Delete the node
    r = await client.request(
        'DELETE',
        f'/api/0.6/node/{node_id}',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@version': 1,
                }
            }
        }),
    )
    assert r.is_success, r.text
    version = int(r.text)
    assert version == 2, 'Deleted node must have version incremented to 2'

    # Verify that the node is no longer in the map response
    r = await client.get('/api/0.6/map', params={'bbox': bbox})
    assert r.is_success, r.text

    map_data = XMLToDict.parse(r.content)['osm']

    # Handle the case where map is empty (returned as dict)
    if not isinstance(map_data, list):
        return

    nodes = [value for key, value in map_data if key == 'node']
    deleted_node = next((node for node in nodes if node['@id'] == node_id), None)
    assert deleted_node is None, 'Deleted node must not appear in map response'
