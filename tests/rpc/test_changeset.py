from httpx import AsyncClient

from app.lib.xmltodict import XMLToDict
from app.models.proto.changeset_pb2 import GetDiffRequest, GetDiffResponse


async def _create_changeset(client: AsyncClient):
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': 'tests'}]}}
        }),
    )
    assert r.is_success, r.text
    return int(r.text)


async def test_changeset_diff_renders_deleted_node_geometry(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    first_changeset_id = await _create_changeset(client)
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': first_changeset_id,
                    '@lon': 1,
                    '@lat': 2,
                }
            }
        }),
    )
    assert r.is_success, r.text
    node_id = int(r.text)

    r = await client.put(f'/api/0.6/changeset/{first_changeset_id}/close')
    assert r.is_success, r.text

    delete_changeset_id = await _create_changeset(client)
    r = await client.request(
        'DELETE',
        f'/api/0.6/node/{node_id}',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': delete_changeset_id,
                    '@version': 1,
                }
            }
        }),
    )
    assert r.is_success, r.text

    r = await client.post(
        '/rpc/changeset.Service/GetDiff',
        headers={'Content-Type': 'application/proto'},
        content=GetDiffRequest(id=delete_changeset_id).SerializeToString(),
    )
    assert r.is_success, r.text

    response = GetDiffResponse.FromString(r.content)
    assert len(response.render.nodes) == 1
    node = response.render.nodes[0]
    assert node.id == node_id
    assert node.location.lon == 1
    assert node.location.lat == 2
