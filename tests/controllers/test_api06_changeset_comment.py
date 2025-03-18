from httpx import AsyncClient

from app.config import LEGACY_HIGH_PRECISION_TIME
from app.lib.xmltodict import XMLToDict


async def test_changeset_comment_crud(client: AsyncClient):
    assert LEGACY_HIGH_PRECISION_TIME
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': test_changeset_comment_crud.__name__}]}}
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Read changeset (before commenting)
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text

    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore
    assert not changeset['@comments_count'], 'Changeset must have no comments initially'
    last_updated_at = changeset['@updated_at']

    # Create comment
    comment_text = 'Test comment for API testing'
    r = await client.post(f'/api/0.6/changeset/{changeset_id}/comment', data={'text': comment_text})
    assert r.is_success, r.text

    changeset = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore
    assert changeset['@id'] == changeset_id
    assert changeset['@updated_at'] > last_updated_at
    assert 'discussion' not in changeset

    # Read changeset with discussion
    r = await client.get(f'/api/0.6/changeset/{changeset_id}', params={'include_discussion': 'true'})
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore

    assert changeset['@comments_count'] == 1, 'Changeset must have exactly one comment'
    comment = changeset['discussion']['comment'][0]
    assert comment['@date'] == changeset['@updated_at'], 'Comment date must match changeset update time'
    assert comment['user'] == 'user1'
    assert comment['text'] == comment_text

    last_updated_at = changeset['@updated_at']
    comment_id = comment['@id']

    # Delete comment (requires moderator)
    client.headers['Authorization'] = 'User moderator'

    r = await client.delete(f'/api/0.6/changeset/comment/{comment_id}')
    assert r.is_success, r.text

    # Read changeset after deletion
    r = await client.get(f'/api/0.6/changeset/{changeset_id}', params={'include_discussion': 'true'})
    assert r.is_success, r.text

    changeset = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore
    assert changeset['@updated_at'] > last_updated_at
    assert not changeset['@comments_count'], 'Changeset must have no comments after deletion'
