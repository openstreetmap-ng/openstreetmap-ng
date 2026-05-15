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
from app.exceptions.api_error import APIError
from app.exceptions.context import exceptions_context
from app.exceptions06 import Exceptions06
from app.format import Format06
from app.lib.auth.context import auth_context
from app.lib.io.xml_codec import XMLToDict
from app.models.types import ChangesetId, DisplayName
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.changeset_service import ChangesetService
from tests.utils.assert_model import assert_model


async def _create_note(client: AsyncClient, text: str) -> int:
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': text},
    )
    assert r.is_success, r.text
    return r.json()['properties']['id']


async def _create_changeset(client: AsyncClient, tags: list[tuple[str, str]]) -> int:
    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {'tag': [{'@k': key, '@v': value} for key, value in tags]}
            }
        }),
    )
    assert r.is_success, r.text
    return int(r.text)


async def _get_note_props(client: AsyncClient, note_id: int) -> dict:
    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.is_success, r.text
    return r.json()['properties']


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


async def test_changeset_close_closes_tagged_notes(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    default_note_id = await _create_note(client, 'default close note')
    specific_note_id = await _create_note(client, 'specific close note')
    already_closed_note_id = await _create_note(client, 'already closed note')

    r = await client.post(
        f'/api/0.6/notes/{already_closed_note_id}/close.json',
        params={'text': 'already closed'},
    )
    assert r.is_success, r.text

    changeset_id = await _create_changeset(
        client,
        [
            ('comment', 'changeset close message'),
            (
                'closes:note',
                f'{default_note_id}; {specific_note_id}; {already_closed_note_id}; '
                f'{default_note_id}; invalid',
            ),
            (f'closes:note:{specific_note_id}:comment', 'specific close message'),
        ],
    )

    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text

    props = await _get_note_props(client, default_note_id)
    assert_model(props, {'status': 'closed'})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'closed',
            'text': 'changeset close message',
        },
    )

    props = await _get_note_props(client, specific_note_id)
    assert_model(props, {'status': 'closed'})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'closed',
            'text': 'specific close message',
        },
    )

    props = await _get_note_props(client, already_closed_note_id)
    assert_model(props, {'status': 'closed'})
    assert len(props['comments']) == 2
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'closed',
            'text': 'already closed',
        },
    )


async def test_changeset_close_uses_global_note_close_comment(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    note_id = await _create_note(client, 'global close note')
    changeset_id = await _create_changeset(
        client,
        [
            ('comment', 'ignored close message'),
            ('closes:note', str(note_id)),
            ('closes:note:comment', 'global close message'),
        ],
    )

    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text

    props = await _get_note_props(client, note_id)
    assert_model(props, {'status': 'closed'})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'closed',
            'text': 'global close message',
        },
    )


async def test_changeset_note_close_subscribes_closer(client: AsyncClient):
    client.headers['Authorization'] = 'User user2'
    note_id = await _create_note(client, 'owned by another user')

    client.headers['Authorization'] = 'User user1'
    changeset_id = await _create_changeset(
        client,
        [
            ('comment', 'subscribe closer'),
            ('closes:note', str(note_id)),
        ],
    )

    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text

    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None

    with auth_context(user, frozenset(('web_user',))):
        assert await UserSubscriptionQuery.is_subscribed('note', note_id)


async def test_changeset_close_requires_note_scope_for_tagged_notes(
    client: AsyncClient,
):
    client.headers['Authorization'] = 'User user1'

    note_id = await _create_note(client, 'scope protected note')
    changeset_id = await _create_changeset(
        client,
        [
            ('comment', 'changeset close message'),
            ('closes:note', str(note_id)),
        ],
    )

    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None

    with (
        exceptions_context(Exceptions06()),
        auth_context(user, frozenset(('write_api',))),
        pytest.raises(APIError) as raised,
    ):
        await ChangesetService.close(ChangesetId(changeset_id))

    assert raised.value.status_code == status.HTTP_403_FORBIDDEN

    props = await _get_note_props(client, note_id)
    assert_model(props, {'status': 'open'})
    assert len(props['comments']) == 1

    r = await client.get(f'/api/0.6/changeset/{changeset_id}')
    assert r.is_success, r.text
    changeset = XMLToDict.parse(r.content)['osm']['changeset']
    assert_model(changeset, {'@open': True})


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
