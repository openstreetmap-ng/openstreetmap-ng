from httpx import AsyncClient

from app.lib.xmltodict import XMLToDict


async def _create_changeset(client: AsyncClient, created_by: str) -> int:
    response = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': created_by}]}}
        }),
    )
    assert response.is_success, response.text
    return int(response.text)


async def _create_node(client: AsyncClient, changeset_id: int) -> int:
    response = await client.put(
        '/api/0.6/node/create',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@lon': 1,
                    '@lat': 2,
                    'tag': [{'@k': 'name', '@v': 'History test node'}],
                }
            }
        }),
    )
    assert response.is_success, response.text
    return int(response.text)


async def _update_node(
    client: AsyncClient,
    *,
    changeset_id: int,
    node_id: int,
    version: int,
    lon: float,
    lat: float,
) -> None:
    response = await client.put(
        f'/api/0.6/node/{node_id}',
        content=XMLToDict.unparse({
            'osm': {
                'node': {
                    '@changeset': changeset_id,
                    '@version': version,
                    '@lon': lon,
                    '@lat': lat,
                    'tag': [{'@k': 'name', '@v': f'History test node v{version + 1}'}],
                }
            }
        }),
    )
    assert response.is_success, response.text
    assert int(response.text) == version + 1


async def test_partial_element_history_accepts_custom_limit(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    changeset_id = await _create_changeset(
        client, test_partial_element_history_accepts_custom_limit.__qualname__
    )
    node_id = await _create_node(client, changeset_id)
    await _update_node(
        client,
        changeset_id=changeset_id,
        node_id=node_id,
        version=1,
        lon=3,
        lat=4,
    )

    client.headers.pop('Authorization')

    response = await client.get(f'/partial/node/{node_id}/history?limit=25')
    assert response.is_success, response.text
    assert 'data-page-size="25"' in response.text
    assert (
        f'/api/web/element/node/{node_id}/history?tags_diff={{tags_diff}}&limit={{history_limit}}'
        in response.text
    )


async def test_web_element_history_uses_limit_as_page_size(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    changeset_id = await _create_changeset(
        client, test_web_element_history_uses_limit_as_page_size.__qualname__
    )
    node_id = await _create_node(client, changeset_id)

    for version, (lon, lat) in enumerate(((3, 4), (5, 6), (7, 8), (9, 10)), start=1):
        await _update_node(
            client,
            changeset_id=changeset_id,
            node_id=node_id,
            version=version,
            lon=lon,
            lat=lat,
        )

    client.headers.pop('Authorization')

    response = await client.post(
        f'/api/web/element/node/{node_id}/history?tags_diff=false&limit=2',
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert response.is_success, response.text
    assert 'X-StandardPagination' in response.headers
    assert response.text.count('class="version-section') == 2
