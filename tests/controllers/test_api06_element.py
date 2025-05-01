from typing import Any

from annotated_types import Gt, Len
from httpx import AsyncClient
from starlette import status

from app.config import LEGACY_HIGH_PRECISION_TIME
from app.format import Format06
from app.lib.xmltodict import XMLToDict
from tests.utils.assert_model import assert_model


def _strip_osmchange_attrs(
    osmchange: list[tuple[str, Any]],
) -> list[tuple[str, Any]]:
    return [(action, value) for action, value in osmchange if action[:1] != '@']


async def test_element_crud(client: AsyncClient):
    assert LEGACY_HIGH_PRECISION_TIME
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [{'@k': 'created_by', '@v': test_element_crud.__name__}]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Read changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore
    last_updated_at = changeset['@updated_at']

    # Create node
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': 1,
                    '@lat': 2,
                    'tag': [
                        {'@k': 'update_me', '@v': 'update_me'},
                        {'@k': 'remove_me', '@v': 'remove_me'},
                    ],
                }
            }
        }),
    )
    assert r.is_success, r.text
    node_id = int(r.text)

    # Read changeset to verify update
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore

    assert_model(
        changeset,
        {
            '@updated_at': Gt(last_updated_at),
            '@changes_count': 1,
            '@min_lon': 1.0,
            '@max_lon': 1.0,
            '@min_lat': 2.0,
            '@max_lat': 2.0,
        },
    )

    # Read node details
    r = await client.get(f'/api/0.6/node/{node_id}')
    assert r.is_success, r.text
    node: dict = next(v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node')  # type: ignore

    assert_model(
        node,
        {
            '@id': node_id,
            '@version': 1,
            '@changeset': changeset_id,
            '@visible': True,
            '@lon': 1.0,
            '@lat': 2.0,
            'tag': Len(2, 2),
        },
    )
    tags = Format06.decode_tags_and_validate(node['tag'])
    assert tags['update_me'] == 'update_me'
    assert tags['remove_me'] == 'remove_me'

    # Read osmChange to verify create action
    r = await client.get(f'/api/0.6/changeset/{changeset_id}/download')
    assert r.is_success, r.text

    action, ((type, node),) = _strip_osmchange_attrs(
        XMLToDict.parse(r.content)['osmChange']  # type: ignore
    )[-1]
    assert action == 'create'
    assert type == 'node'
    assert_model(
        node,
        {
            '@id': node_id,
            '@version': 1,
            '@changeset': changeset_id,
            '@timestamp': changeset['@updated_at'],
            '@visible': True,
            '@lon': 1.0,
            '@lat': 2.0,
            'tag': Len(2, 2),
        },
    )
    tags = Format06.decode_tags_and_validate(node['tag'])
    assert tags['update_me'] == 'update_me'
    assert tags['remove_me'] == 'remove_me'

    last_updated_at = changeset['@updated_at']

    # Update node
    r = await client.put(
        f'/api/0.6/node/{node_id}',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@version': 1,
                    '@lon': 3,
                    '@lat': 4,
                    'tag': [{'@k': 'update_me', '@v': 'updated'}],
                }
            }
        }),
    )
    assert r.is_success, r.text
    version = int(r.text)
    assert version == 2, 'Update must return version 2'

    # Read changeset to verify update
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore

    assert_model(
        changeset,
        {
            '@updated_at': Gt(last_updated_at),
            '@changes_count': 2,
            '@min_lon': 1.0,
            '@max_lon': 3.0,
            '@min_lat': 2.0,
            '@max_lat': 4.0,
        },
    )

    # Read osmChange to verify modify action
    r = await client.get(f'/api/0.6/changeset/{changeset_id}/download')
    assert r.is_success, r.text

    action, ((type, node),) = _strip_osmchange_attrs(
        XMLToDict.parse(r.content)['osmChange']  # type: ignore
    )[-1]
    assert action == 'modify'
    assert type == 'node'
    assert_model(
        node,
        {
            '@id': node_id,
            '@version': 2,
            '@user': 'user1',
            '@changeset': changeset_id,
            '@timestamp': changeset['@updated_at'],
            '@visible': True,
            '@lon': 3.0,
            '@lat': 4.0,
            'tag': Len(1, 1),
        },
    )
    tags = Format06.decode_tags_and_validate(node['tag'])
    assert tags['update_me'] == 'updated'
    assert 'remove_me' not in tags

    last_updated_at = changeset['@updated_at']

    # Delete node
    r = await client.request(
        'DELETE',
        f'/api/0.6/node/{node_id}',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@version': 2,
                }
            }
        }),
    )
    assert r.is_success, r.text
    version = int(r.text)
    assert version == 3, 'Delete must return version 3'

    # Read changeset to verify delete
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore

    assert_model(
        changeset,
        {
            '@updated_at': Gt(last_updated_at),
            '@changes_count': 3,
        },
    )

    # Verify node is gone
    r = await client.get(f'/api/0.6/node/{node_id}')
    assert r.status_code == status.HTTP_410_GONE

    # Read osmChange to verify delete action
    r = await client.get(f'/api/0.6/changeset/{changeset_id}/download')
    assert r.is_success, r.text

    action, ((type, node),) = _strip_osmchange_attrs(
        XMLToDict.parse(r.content)['osmChange']  # type: ignore
    )[-1]
    assert action == 'delete'
    assert_model(
        node,
        {
            '@id': node_id,
            '@version': 3,
            '@changeset': changeset_id,
            '@timestamp': changeset['@updated_at'],
            '@visible': False,
        },
    )
    assert '@lon' not in node
    assert '@lat' not in node
    assert 'tag' not in node


async def test_element_create_many_post(client: AsyncClient):
    assert LEGACY_HIGH_PRECISION_TIME
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {
                            '@k': 'created_by',
                            '@v': test_element_create_many_post.__name__,
                        },
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Create multiple nodes
    r = await client.post(
        '/api/0.6/nodes',
        content=XMLToDict.unparse({
            'osm': {
                'node': (
                    {
                        '@changeset': changeset_id,
                        '@lon': 1,
                        '@lat': 2,
                        'tag': [{'@k': 'id', '@v': '1'}],
                    },
                    {
                        '@changeset': changeset_id,
                        '@lon': 2,
                        '@lat': 3,
                        'tag': [{'@k': 'id', '@v': '2'}],
                    },
                )
            }
        }),
    )
    assert r.is_success, r.text
    node_id = int(r.text)  # The response only contains the first node id

    for offset in range(2):
        # Read and verify the node
        r = await client.get(f'/api/0.6/node/{node_id + offset}')
        assert r.is_success, r.text
        node: dict = next(
            v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node'
        )  # type: ignore

        assert_model(
            node,
            {
                '@id': node_id + offset,
                '@version': 1,
                '@changeset': changeset_id,
                '@visible': True,
                'tag': [{'@k': 'id', '@v': str(offset + 1)}],
            },
        )


async def test_element_version_and_history(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {
                            '@k': 'created_by',
                            '@v': test_element_version_and_history.__name__,
                        }
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Create a node (version 1)
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': 1,
                    '@lat': 2,
                    'tag': [{'@k': 'version', '@v': '1'}],
                }
            }
        }),
    )
    assert r.is_success, r.text
    node_id = int(r.text)

    # Update the node (version 2)
    r = await client.put(
        f'/api/0.6/node/{node_id}',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@version': 1,
                    '@lon': 3,
                    '@lat': 4,
                    'tag': [{'@k': 'version', '@v': '2'}],
                }
            }
        }),
    )
    assert r.is_success, r.text
    assert int(r.text) == 2, 'Update must return version 2'

    # Get specific version (version 1)
    r = await client.get(f'/api/0.6/node/{node_id}/1')
    assert r.is_success, r.text
    node: dict = next(v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node')  # type: ignore

    assert_model(
        node,
        {
            '@id': node_id,
            '@version': 1,
            '@lon': 1.0,
            '@lat': 2.0,
            'tag': [{'@k': 'version', '@v': '1'}],
        },
    )

    # Get specific version (version 2)
    r = await client.get(f'/api/0.6/node/{node_id}/2')
    assert r.is_success, r.text
    node = next(v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node')  # type: ignore

    assert_model(
        node,
        {
            '@id': node_id,
            '@version': 2,
            '@lon': 3.0,
            '@lat': 4.0,
            'tag': [{'@k': 'version', '@v': '2'}],
        },
    )

    # Get history
    r = await client.get(f'/api/0.6/node/{node_id}/history')
    assert r.is_success, r.text
    nodes: list[dict] = [v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node']  # type: ignore

    # History must return an array of all versions
    assert len(nodes) == 2, 'History must contain 2 versions'
    assert_model(nodes[0], {'@version': 1})
    assert_model(nodes[1], {'@version': 2})


async def test_get_multiple_elements(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'created_by', '@v': test_get_multiple_elements.__name__},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Create the first node
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': 1,
                    '@lat': 2,
                }
            }
        }),
    )
    assert r.is_success, r.text
    node1_id = int(r.text)

    # Create the second node
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': 3,
                    '@lat': 4,
                }
            }
        }),
    )
    assert r.is_success, r.text
    node2_id = int(r.text)

    # Get multiple nodes
    r = await client.get(f'/api/0.6/nodes?nodes={node2_id},{node1_id}')
    assert r.is_success, r.text
    nodes: list[dict] = [v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node']  # type: ignore

    assert len(nodes) == 2, 'Response must contain 2 nodes'
    assert_model(nodes[0], {'@id': node2_id})
    assert_model(nodes[1], {'@id': node1_id})

    # Get multiple nodes with version specifier
    r = await client.get(f'/api/0.6/nodes?nodes={node2_id}v1,{node1_id}v1')
    assert r.is_success, r.text
    nodes = [v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node']  # type: ignore

    assert len(nodes) == 2, 'Response must contain 2 nodes'
    assert_model(nodes[0], {'@id': node2_id, '@version': 1})
    assert_model(nodes[1], {'@id': node1_id, '@version': 1})

    # Test non-existent node reference
    r = await client.get(f'/api/0.6/nodes?nodes={node2_id}v1,{node1_id}v2')
    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_element_visibility(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'created_by', '@v': test_element_visibility.__name__},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Create a node
    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': 1,
                    '@lat': 2,
                }
            }
        }),
    )
    assert r.is_success, r.text
    node_id = int(r.text)

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

    # Verify deleted node is gone
    r = await client.get(f'/api/0.6/node/{node_id}')
    assert r.status_code == status.HTTP_410_GONE
    r = await client.get(f'/api/0.6/node/{node_id}/full')
    assert r.status_code == status.HTTP_410_GONE

    # Verify specific version is still accessible
    r = await client.get(f'/api/0.6/node/{node_id}/1')
    assert r.is_success, r.text
    r = await client.get(f'/api/0.6/node/{node_id}/2')
    assert r.is_success, r.text

    # Verify history is still accessible
    r = await client.get(f'/api/0.6/node/{node_id}/history')
    assert r.is_success, r.text
    nodes: list[dict] = [v for k, v in XMLToDict.parse(r.content)['osm'] if k == 'node']  # type: ignore

    # History must return an array of all versions
    assert len(nodes) == 2, 'History must contain 2 versions'
    assert_model(nodes[0], {'@id': node_id, '@version': 1, '@visible': True})
    assert_model(nodes[1], {'@id': node_id, '@version': 2, '@visible': False})
