from datetime import datetime

import pytest
from annotated_types import Gt
from httpx import AsyncClient
from starlette import status

from app.config import (
    LEGACY_HIGH_PRECISION_TIME,
    TAGS_KEY_MAX_LENGTH,
    TAGS_LIMIT,
    TAGS_MAX_SIZE,
)
from app.format import Format06
from app.lib.xmltodict import XMLToDict
from tests.utils.assert_model import assert_model


async def test_changeset_crud(client: AsyncClient):
    assert LEGACY_HIGH_PRECISION_TIME
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'comment', '@v': 'create'},
                        {'@k': 'created_by', '@v': test_changeset_crud.__name__},
                        {'@k': 'remove_me', '@v': 'remove_me'},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Read the changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']
    tags = Format06.decode_tags_and_validate(changeset['tag'])

    assert_model(
        changeset,
        {
            '@id': changeset_id,
            '@user': 'user1',
            '@open': True,
            '@created_at': changeset['@updated_at'],  # Equal to updated_at on creation
        },
    )
    assert '@closed_at' not in changeset
    assert len(tags) == 3
    assert tags['comment'] == 'create'

    last_updated_at = changeset['@updated_at']

    # Update the changeset
    r = await client.put(
        f'/api/0.6/changeset/{changeset_id}',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'comment', '@v': 'update'},
                        {'@k': 'created_by', '@v': test_changeset_crud.__name__},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']
    tags = Format06.decode_tags_and_validate(changeset['tag'])

    assert_model(changeset, {'@updated_at': Gt(last_updated_at)})
    assert len(tags) == 2
    assert tags['comment'] == 'update'
    assert 'remove_me' not in tags

    last_updated_at = changeset['@updated_at']

    # Close the changeset
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text
    assert not r.content

    # Read the closed changeset
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']

    assert_model(
        changeset,
        {
            '@open': False,
            '@updated_at': Gt(last_updated_at),
            '@closed_at': datetime,
            '@changes_count': 0,
        },
    )
    assert '@min_lat' not in changeset
    assert '@max_lat' not in changeset
    assert '@min_lon' not in changeset
    assert '@max_lon' not in changeset


async def test_changeset_upload(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [{'@k': 'created_by', '@v': test_changeset_upload.__name__}]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Upload changes to the changeset
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/upload',
        content=XMLToDict.unparse({
            'osmChange': {
                'create': [
                    ('node', {'@id': -1, '@lat': 0, '@lon': 0}),
                    ('way', {'@id': -1, 'nd': [{'@ref': -1}]}),
                ]
            }
        }),
    )
    assert r.is_success, r.text

    # Close the changeset
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text
    assert not r.content

    # Read the changeset to verify changes were applied
    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']

    assert_model(
        changeset,
        {
            '@open': False,
            '@updated_at': datetime,
            '@closed_at': datetime,
            '@changes_count': 2,
            '@min_lat': 0.0,
            '@max_lat': 0.0,
            '@min_lon': 0.0,
            '@max_lon': 0.0,
        },
    )


@pytest.mark.parametrize('include', [True, False])
async def test_changeset_with_discussion(client: AsyncClient, include):
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
                            '@v': test_changeset_with_discussion.__name__,
                        }
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Add a comment to the changeset
    comment_text = 'This is a test comment'
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/comment',
        data={'text': comment_text},
    )
    assert r.is_success, r.text

    # Get the changeset with discussion
    r = await client.get(
        f'/api/0.6/changeset/{changeset_id}',
        params={'include_discussion': 'true'} if include else None,
    )
    assert r.is_success, r.text
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']

    if include:
        # Verify the comment exists
        assert len(changeset['discussion']['comment']) == 1
        comment = changeset['discussion']['comment'][0]
        assert_model(
            comment,
            {
                '@user': 'user1',
                'text': comment_text,
            },
        )
    else:
        assert 'discussion' not in changeset


async def test_changeset_update_closed(client: AsyncClient):
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
                            '@v': test_changeset_update_closed.__name__,
                        }
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Close the changeset
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text

    # Try to update the closed changeset
    r = await client.put(
        f'/api/0.6/changeset/{changeset_id}',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': 'updated', '@v': 'value'}]}}
        }),
    )
    assert r.status_code == status.HTTP_409_CONFLICT, r.text


async def test_changeset_upload_closed(client: AsyncClient):
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
                            '@v': test_changeset_upload_closed.__name__,
                        }
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Close the changeset
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text

    # Try to upload to the closed changeset
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/upload',
        content=XMLToDict.unparse({
            'osmChange': {'create': [('node', {'@id': -1, '@lat': 0, '@lon': 0})]}
        }),
    )
    assert r.status_code == status.HTTP_409_CONFLICT, r.text


async def test_changeset_close_twice(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Create a changeset
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'created_by', '@v': test_changeset_close_twice.__name__}
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    # Close the changeset first time
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text

    # Try to close the changeset again
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.status_code == status.HTTP_409_CONFLICT, r.text


async def test_changesets_not_found(client: AsyncClient):
    r = await client.get('/api/0.6/changeset/0')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text


@pytest.mark.parametrize(
    ('key_length', 'value_length', 'should_succeed'),
    [
        (TAGS_KEY_MAX_LENGTH, 255, True),  # At limits
        (TAGS_KEY_MAX_LENGTH + 1, 255, False),  # Key too long
        (TAGS_KEY_MAX_LENGTH, 256, False),  # Value too long
    ],
)
async def test_changesets_tag_max_length(
    client: AsyncClient, key_length, value_length, should_succeed
):
    client.headers['Authorization'] = 'User user1'

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [{'@k': '0' * key_length, '@v': '0' * value_length}]
                }
            }
        }),
    )

    if should_succeed:
        assert r.is_success, r.text
    else:
        assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text


@pytest.mark.parametrize(
    ('num_tags', 'should_succeed'),
    [
        (TAGS_LIMIT, True),  # At limit
        (TAGS_LIMIT + 1, False),  # Too many tags
    ],
)
async def test_changesets_tags_limit(client: AsyncClient, num_tags, should_succeed):
    client.headers['Authorization'] = 'User user1'

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [{'@k': str(i), '@v': str(i)} for i in range(num_tags)]
                }
            }
        }),
    )

    if should_succeed:
        assert r.is_success, r.text
    else:
        assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text


@pytest.mark.parametrize(
    ('num_tags', 'should_succeed'),
    [
        (TAGS_MAX_SIZE // (TAGS_KEY_MAX_LENGTH * 2), True),  # At limit
        (TAGS_MAX_SIZE // (TAGS_KEY_MAX_LENGTH * 2) + 1, False),  # Too much data
    ],
)
async def test_changesets_tags_size(client: AsyncClient, num_tags, should_succeed):
    client.headers['Authorization'] = 'User user1'

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {
                            '@k': f'{i:0{TAGS_KEY_MAX_LENGTH}d}',
                            '@v': f'{i:0{TAGS_KEY_MAX_LENGTH}d}',
                        }
                        for i in range(num_tags)
                    ]
                }
            }
        }),
    )

    if should_succeed:
        assert r.is_success, r.text
    else:
        assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
