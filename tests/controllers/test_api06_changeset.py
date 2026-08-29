from datetime import datetime, timedelta

import pytest
from annotated_types import Gt, Len
from httpx import AsyncClient
from starlette import status

from app.config import (
    CHANGESET_IDLE_TIMEOUT,
    LEGACY_HIGH_PRECISION_TIME,
    TAGS_KEY_MAX_LENGTH,
    TAGS_LIMIT,
    TAGS_MAX_SIZE,
)
from app.db import db
from app.format import Format06
from app.lib.auth.user_limits import UserRoleLimits
from app.lib.io.xml_codec import XMLToDict
from app.services.changeset_service import ChangesetService
from app.services.note_service import NoteService
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


async def test_changeset_close_closes_tagged_notes(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    async def create_note(text: str) -> int:
        r = await client.post(
            '/api/0.6/notes.json', json={'lon': 0, 'lat': 0, 'text': text}
        )
        assert r.is_success, r.text
        return r.json()['properties']['id']

    fallback_note_id = await create_note('fallback close note')
    global_note_id = await create_note('global close note')
    specific_note_id = await create_note('specific close note')
    already_closed_note_id = await create_note('already closed note')

    r = await client.post(
        f'/api/0.6/notes/{already_closed_note_id}/close.json',
        params={'text': 'closed before changeset'},
    )
    assert r.is_success, r.text
    already_closed_comments = r.json()['properties']['comments']

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'comment', '@v': 'changeset fallback'},
                        {'@k': 'closes:note', '@v': str(fallback_note_id)},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    fallback_changeset_id = int(r.text)

    r = await client.put(f'/api/0.6/changeset/{fallback_changeset_id}/close')
    assert r.is_success, r.text

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'comment', '@v': 'changeset fallback'},
                        {
                            '@k': 'closes:note',
                            '@v': (
                                f'{global_note_id};invalid;0;-1;{specific_note_id};'
                                f'{specific_note_id};{already_closed_note_id};'
                                '9223372036854775808;999999999999'
                            ),
                        },
                        {'@k': 'closes:note:comment', '@v': 'global close message'},
                        {
                            '@k': f'closes:note:{specific_note_id}:comment',
                            '@v': 'specific close message',
                        },
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text

    for note_id, expected_comment in (
        (fallback_note_id, 'changeset fallback'),
        (global_note_id, 'global close message'),
        (specific_note_id, 'specific close message'),
    ):
        r = await client.get(f'/api/0.6/notes/{note_id}.json')
        assert r.is_success, r.text
        note = r.json()['properties']
        assert_model(note, {'status': 'closed', 'comments': Len(2, 2)})
        assert_model(
            note['comments'][-1],
            {'user': 'user1', 'action': 'closed', 'text': expected_comment},
        )

    r = await client.get(f'/api/0.6/notes/{already_closed_note_id}.json')
    assert r.is_success, r.text
    assert r.json()['properties']['comments'] == already_closed_comments


async def test_changeset_tagged_notes_require_write_notes(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    client.headers['Authorization'] = 'User user1'
    monkeypatch.setattr(
        'app.services.changeset_service.auth_scopes',
        lambda: frozenset({'write_api'}),
    )

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [{'@k': 'closes:note', '@v': '1'}],
                }
            }
        }),
    )

    assert r.status_code == status.HTTP_403_FORBIDDEN, r.text
    assert (
        'The request requires higher privileges than authorized (write_notes)' in r.text
    )


async def test_changeset_note_closes_are_atomic(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    client.headers['Authorization'] = 'User user1'

    note_ids: list[int] = []
    for index in range(2):
        r = await client.post(
            '/api/0.6/notes.json',
            json={'lon': index, 'lat': 0, 'text': f'atomic note {index}'},
        )
        assert r.is_success, r.text
        note_ids.append(r.json()['properties']['id'])

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'closes:note', '@v': ';'.join(map(str, note_ids))},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    original_comment = NoteService.comment

    async def fail_after_second_note(*args, **kwargs):
        result = await original_comment(*args, **kwargs)
        if args[0] == note_ids[1]:
            raise RuntimeError('injected note close failure')
        return result

    monkeypatch.setattr(
        NoteService,
        'comment',
        staticmethod(fail_after_second_note),
    )

    with pytest.raises(RuntimeError, match='injected note close failure'):
        await client.put(f'/api/0.6/changeset/{changeset_id}/close')

    r = await client.get(f'/api/0.6/changeset/{changeset_id}.json')
    assert r.is_success, r.text
    assert r.json()['changesets'][0]['open'] is True

    for note_id in note_ids:
        r = await client.get(f'/api/0.6/notes/{note_id}.json')
        assert r.is_success, r.text
        assert_model(r.json()['properties'], {'status': 'open', 'comments': Len(1, 1)})


async def test_changeset_size_limit_closes_tagged_note(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes.json',
        json={
            'lon': 0,
            'lat': 0,
            'text': test_changeset_size_limit_closes_tagged_note.__name__,
        },
    )
    assert r.is_success, r.text
    note_id = r.json()['properties']['id']

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'comment', '@v': 'size limit close message'},
                        {'@k': 'closes:note', '@v': str(note_id)},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    monkeypatch.setattr(
        UserRoleLimits,
        'get_changeset_max_size',
        staticmethod(lambda _roles: 1),
    )
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/upload',
        content=XMLToDict.unparse({
            'osmChange': {
                'create': [('node', {'@id': -1, '@lat': 0, '@lon': 0})],
            }
        }),
    )
    assert r.is_success, r.text

    r = await client.get(f'/api/0.6/changeset/{changeset_id}.json')
    assert r.is_success, r.text
    assert r.json()['changesets'][0]['open'] is False

    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.is_success, r.text
    note = r.json()['properties']
    assert_model(note, {'status': 'closed', 'comments': Len(2, 2)})
    assert_model(
        note['comments'][-1],
        {
            'user': 'user1',
            'action': 'closed',
            'text': 'size limit close message',
        },
    )


async def test_inactive_changeset_closes_tagged_note(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes.json',
        json={
            'lon': 0,
            'lat': 0,
            'text': test_inactive_changeset_closes_tagged_note.__name__,
        },
    )
    assert r.is_success, r.text
    note_id = r.json()['properties']['id']

    r = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {
                'changeset': {
                    'tag': [
                        {'@k': 'comment', '@v': 'inactive close message'},
                        {'@k': 'closes:note', '@v': str(note_id)},
                    ]
                }
            }
        }),
    )
    assert r.is_success, r.text
    changeset_id = int(r.text)

    async with db(True) as conn:
        assert conn is not None
        await conn.execute(
            t"""
                UPDATE changeset
                SET updated_at = statement_timestamp() - {CHANGESET_IDLE_TIMEOUT + timedelta(seconds=1)}
                WHERE id = {changeset_id}
            """
        )

    await ChangesetService.force_process()

    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.is_success, r.text
    note = r.json()['properties']
    assert_model(note, {'status': 'closed', 'comments': Len(2, 2)})
    assert_model(
        note['comments'][-1],
        {'user': 'user1', 'action': 'closed', 'text': 'inactive close message'},
    )


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
