import pytest
from httpx import AsyncClient

from app.lib.io.xml_codec import XMLToDict
from app.models.proto.element_pb2 import GetHistoryRequest, GetHistoryResponse
from app.models.proto.shared_pb2 import StandardPaginationRequest


async def _node_history(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    response = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': 'history-tests'}]}}
        }),
    )
    assert response.is_success, response.text
    changeset_id = int(response.text)
    node_id = None
    for version in range(12):
        node = {
            '@changeset': changeset_id,
            '@lat': 1,
            '@lon': 2,
            'tag': [{'@k': 'test_version', '@v': str(version + 1)}],
        }
        if node_id is not None:
            node.update({'@id': node_id, '@version': version})
        response = await client.put(
            '/api/0.6/node/create' if node_id is None else f'/api/0.6/node/{node_id}',
            content=XMLToDict.unparse({'osm': {'node': node}}),
        )
        assert response.is_success, response.text
        if node_id is None:
            node_id = int(response.text)
    assert node_id is not None
    return node_id


async def _history(client: AsyncClient, node_id: int, **kwargs):
    response = await client.post(
        '/rpc/element.Service/GetHistory',
        headers={'Content-Type': 'application/proto'},
        content=GetHistoryRequest(
            element={'type': 'node', 'id': node_id}, **kwargs
        ).SerializeToString(),
    )
    assert response.is_success, response.text
    return GetHistoryResponse.FromString(response.content)


async def test_history_default_and_custom_limits(client: AsyncClient):
    node_id = await _node_history(client)
    default = await _history(client, node_id)
    assert [entry.ref.version for entry in default.elements] == list(range(12, 2, -1))
    assert default.state.page_size == 10
    assert default.state.known_total.num_pages == 2

    first = await _history(client, node_id, limit=5, tags_diff=True)
    assert [entry.ref.version for entry in first.elements] == [12, 11, 10, 9, 8]
    assert first.state.page_size == 5
    assert first.state.known_total.num_items == 12
    assert first.state.known_total.num_pages == 3
    assert first.elements[-1].tags_old['test_version'] == '7'

    second = await _history(
        client,
        node_id,
        limit=5,
        state=StandardPaginationRequest(state=first.state, requested_page=2),
    )
    assert [entry.ref.version for entry in second.elements] == [7, 6, 5, 4, 3]
    last = await _history(
        client,
        node_id,
        limit=5,
        state=StandardPaginationRequest(state=second.state, requested_page=3),
    )
    assert [entry.ref.version for entry in last.elements] == [2, 1]

    # Both the cursor and requested page refer to five-item pages. Reset them.
    changed = await _history(
        client,
        node_id,
        limit=100,
        state=StandardPaginationRequest(state=last.state, requested_page=3),
    )
    assert [entry.ref.version for entry in changed.elements] == list(range(12, 0, -1))
    assert changed.state.page_size == 100
    assert changed.state.current_page == 1
    assert changed.state.known_total.num_pages == 1

    single = await _history(client, node_id, limit=1)
    assert [entry.ref.version for entry in single.elements] == [12]
    assert single.state.known_total.num_pages == 12


@pytest.mark.parametrize('limit', [0, 101, 2**32 - 1])
async def test_history_invalid_limit(client: AsyncClient, limit: int):
    response = await client.post(
        '/rpc/element.Service/GetHistory',
        headers={'Content-Type': 'application/proto'},
        content=GetHistoryRequest(
            element={'type': 'node', 'id': 1}, limit=limit
        ).SerializeToString(),
    )
    assert response.status_code == 400, response.text
