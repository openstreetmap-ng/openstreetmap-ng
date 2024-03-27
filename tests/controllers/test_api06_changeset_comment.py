import anyio
import pytest
from httpx import AsyncClient

from app.lib.xmltodict import XMLToDict

pytestmark = pytest.mark.anyio


async def test_changeset_comment_crud(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse(
            {
                'osm': {
                    'changeset': {
                        'tag': [
                            {'@k': 'created_by', '@v': test_changeset_comment_crud.__name__},
                        ]
                    }
                }
            }
        ),
    )
    assert r.is_success
    changeset_id = int(r.text)

    # read changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']

    last_updated_at = changeset['@updated_at']
    await anyio.sleep(1)

    # create comment
    r = await client.post(f'/api/0.6/changeset/{changeset_id}/comment', data={'text': 'comment'})
    assert r.is_success
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']

    assert changeset['@id'] == changeset_id
    assert changeset['@updated_at'] > last_updated_at
    assert 'discussion' not in changeset

    # read changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}', params={'include_discussion': 'true'})
    assert r.is_success
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']

    # TODO: assert changeset['@comments_count'] == 1
    assert len(changeset['discussion']['comment']) == 1
    assert changeset['discussion']['comment'][-1]['@date'] == changeset['@updated_at']
    assert changeset['discussion']['comment'][-1]['text'] == 'comment'

    last_updated_at = changeset['@updated_at']
    comment_id = changeset['discussion']['comment'][-1]['@id']
    await anyio.sleep(1)

    # delete comment
    client.headers['Authorization'] = 'User moderator'

    r = await client.delete(f'/api/0.6/changeset/comment/{comment_id}')
    assert r.is_success

    assert changeset['@id'] == changeset_id

    # read changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}', params={'include_discussion': 'true'})
    assert r.is_success
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']

    assert changeset['@updated_at'] > last_updated_at
    # TODO: assert changeset['@comments_count'] == 0
    assert 'comment' not in changeset['discussion']
