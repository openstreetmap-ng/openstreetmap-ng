from annotated_types import Gt
from httpx import AsyncClient

from app.config import LEGACY_HIGH_PRECISION_TIME
from app.lib.xmltodict import XMLToDict
from tests.utils.assert_model import assert_model


async def test_changeset_comment_crud(client: AsyncClient):
    assert LEGACY_HIGH_PRECISION_TIME
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'created_by', '@v': test_changeset_comment_crud.__name__}
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Read changeset (before commenting)
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']
    changeset_updated_at = changeset['@updated_at']

    assert_model(
        changeset,
        {
            '@id': changeset_id,
            '@comments_count': 0,
        },
    )

    # Create comment
    comment_text = 'Test comment for API testing'
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/comment', data={'text': comment_text}
    )
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']

    assert_model(
        changeset,
        {
            '@id': changeset_id,
            '@comments_count': 1,
            '@updated_at': changeset_updated_at,
        },
    )
    assert 'discussion' not in changeset

    # Read changeset with discussion
    r = await client.get(
        f'/api/0.6/changeset/{changeset_id}', params={'include_discussion': 'true'}
    )
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']
    comment = changeset['discussion']['comment'][0]

    assert_model(
        changeset,
        {
            '@id': changeset_id,
            '@comments_count': 1,
            '@updated_at': changeset_updated_at,
        },
    )
    assert_model(
        comment,
        {
            '@date': Gt(changeset_updated_at),
            '@user': 'user1',
            'text': comment_text,
        },
    )

    comment_id = comment['@id']

    # Delete comment (requires moderator)
    client.headers['Authorization'] = 'User moderator'

    r = await client.delete(f'/api/0.6/changeset/comment/{comment_id}')
    assert r.is_success, r.text

    # Read changeset after deletion
    r = await client.get(
        f'/api/0.6/changeset/{changeset_id}', params={'include_discussion': 'true'}
    )
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']

    assert_model(
        changeset,
        {
            '@id': changeset_id,
            '@comments_count': 0,
            '@updated_at': changeset_updated_at,
        },
    )
