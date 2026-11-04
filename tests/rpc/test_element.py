from httpx import AsyncClient
from starlette import status

from app.lib.io.xml_codec import XMLToDict
from app.models.proto.element_pb2 import GetHistoryRequest, GetHistoryResponse
from app.models.proto.shared_pb2 import (
    ElementRef,
    ElementType,
    StandardPaginationRequest,
)


async def _create_node_with_versions(client: AsyncClient, num_versions: int) -> int:
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [{'@k': 'created_by', '@v': 'test_element_history'}]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    r = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': 1.0,
                    '@lat': 2.0,
                    'tag': [{'@k': 'v', '@v': '1'}],
                }
            }
        }),
    )
    assert r.is_success, r.text
    node_id = int(r.text)

    for version in range(1, num_versions):
        r = await client.put(
            f'/api/0.6/node/{node_id}',
            content=XMLToDict.unparse({
                'osm': {
                    'node': {
                        '@id': node_id,
                        '@version': version,
                        '@changeset': changeset_id,
                        '@lon': 1.0 + version * 0.01,
                        '@lat': 2.0 + version * 0.01,
                        'tag': [{'@k': 'v', '@v': str(version + 1)}],
                    }
                }
            }),
        )
        assert r.is_success, r.text

    return node_id


async def test_element_history_custom_limit(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    node_id = await _create_node_with_versions(client, num_versions=5)
    element_ref = ElementRef(type=ElementType.node, id=node_id)

    # Default limit returns all 5 versions on page 1
    r = await client.post(
        '/rpc/element.Service/GetHistory',
        headers={'Content-Type': 'application/proto'},
        content=GetHistoryRequest(element=element_ref).SerializeToString(),
    )
    assert r.is_success, r.text
    resp = GetHistoryResponse.FromString(r.content)
    assert [e.ref.version for e in resp.elements] == [5, 4, 3, 2, 1]
    assert resp.state.current_page == 1
    assert resp.state.known_total.num_items == 5
    assert resp.state.known_total.num_pages == 1

    # Custom limit=2 paginates 2 versions per page
    r = await client.post(
        '/rpc/element.Service/GetHistory',
        headers={'Content-Type': 'application/proto'},
        content=GetHistoryRequest(element=element_ref, limit=2).SerializeToString(),
    )
    assert r.is_success, r.text
    page1 = GetHistoryResponse.FromString(r.content)
    assert [e.ref.version for e in page1.elements] == [5, 4]
    assert page1.state.current_page == 1
    assert page1.state.page_size == 2
    assert page1.state.known_total.num_items == 5
    assert page1.state.known_total.num_pages == 3

    # Fetch page 2 using returned pagination state
    r = await client.post(
        '/rpc/element.Service/GetHistory',
        headers={'Content-Type': 'application/proto'},
        content=GetHistoryRequest(
            element=element_ref,
            limit=2,
            state=StandardPaginationRequest(requested_page=2, state=page1.state),
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    page2 = GetHistoryResponse.FromString(r.content)
    assert [e.ref.version for e in page2.elements] == [3, 2]
    assert page2.state.current_page == 2
    assert page2.state.page_size == 2

    # Changing limit while passing stale state resets pagination state cleanly
    r = await client.post(
        '/rpc/element.Service/GetHistory',
        headers={'Content-Type': 'application/proto'},
        content=GetHistoryRequest(
            element=element_ref,
            limit=3,
            state=StandardPaginationRequest(requested_page=1, state=page1.state),
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    reset_page = GetHistoryResponse.FromString(r.content)
    assert [e.ref.version for e in reset_page.elements] == [5, 4, 3]
    assert reset_page.state.current_page == 1
    assert reset_page.state.page_size == 3
    assert reset_page.state.known_total.num_pages == 2


async def test_element_history_limit_validation(client: AsyncClient):
    element_ref = ElementRef(type=ElementType.node, id=1)

    for invalid_limit in (0, 101):
        r = await client.post(
            '/rpc/element.Service/GetHistory',
            headers={'Content-Type': 'application/proto'},
            content=GetHistoryRequest(
                element=element_ref, limit=invalid_limit
            ).SerializeToString(),
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
