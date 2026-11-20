import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.config import CHANGESET_IDLE_TIMEOUT
from app.db import db_update
from app.lib.auth.context import auth_context
from app.lib.auth.user_limits import UserRoleLimits
from app.lib.time.date_utils import utcnow
from app.queries.changeset_query import ChangesetQuery
from app.services import changeset_notes
from app.services.changeset_notes import changeset_note_comments
from app.services.changeset_service import ChangesetService, _close_inactive
from app.services.note_service import NoteService


@pytest.mark.parametrize(
    ('tags', 'expected'),
    [
        ({}, {}),
        ({'closes:note': '1;2;1;bad;0;-3;\uff11;9223372036854775808'}, {1: '', 2: ''}),
        (
            {'closes:note': ' 1 ; 02 ', 'comment': 'default'},
            {1: 'default', 2: 'default'},
        ),
        (
            {'closes:note': '1', 'comment': 'fallback', 'closes:note:comment': ''},
            {1: ''},
        ),
        (
            {
                'closes:note': '1;2',
                'comment': 'fallback',
                'closes:note:comment': 'global',
                'closes:note:1:comment': 'individual',
            },
            {1: 'individual', 2: 'global'},
        ),
    ],
)
def test_comment_precedence(tags, expected):
    assert changeset_note_comments(tags) == expected


async def _note(client):
    r = await client.post(
        '/api/0.6/notes.json', json={'lon': 1, 'lat': 1, 'text': 'test'}
    )
    assert r.is_success, r.text
    return r.json()['properties']['id']


async def _properties(client, id):
    r = await client.get(f'/api/0.6/notes/{id}.json')
    assert r.is_success, r.text
    return r.json()['properties']


async def test_concurrent_changesets_close_note_once(
    client: AsyncClient, changeset_id, monkeypatch
):
    id = await _note(client)
    tags = {'closes:note': str(id), 'comment': 'concurrent close'}
    await ChangesetService.update_tags(changeset_id, tags)
    second = await ChangesetService.create(tags)
    barrier = asyncio.Barrier(2)
    original_fetch = changeset_notes.db_fetchone

    async def synchronize_note_lock(*args, **kwargs):
        await barrier.wait()
        return await original_fetch(*args, **kwargs)

    monkeypatch.setattr(changeset_notes, 'db_fetchone', synchronize_note_lock)
    notify = AsyncMock()
    monkeypatch.setattr(NoteService, 'notify_activity', notify)
    async with asyncio.timeout(20):
        await asyncio.gather(
            ChangesetService.close(changeset_id), ChangesetService.close(second)
        )
    props = await _properties(client, id)
    assert props['status'] == 'closed'
    assert len(props['comments']) == 2
    assert props['comments'][-1]['action'] == 'closed'
    assert notify.call_count == 1
    for closed_id in (changeset_id, second):
        changeset = await ChangesetQuery.find_by_id(closed_id)
        assert changeset is not None and changeset['closed_at'] is not None


async def test_hidden_note_is_not_closed(
    client: AsyncClient, changeset_id, monkeypatch
):
    id = await _note(client)
    client.headers['Authorization'] = 'User moderator'
    r = await client.delete(f'/api/0.6/notes/{id}.json')
    assert r.is_success, r.text
    before = await _properties(client, id)
    await ChangesetService.update_tags(changeset_id, {'closes:note': str(id)})
    notify = AsyncMock()
    monkeypatch.setattr(NoteService, 'notify_activity', notify)
    # Direct service call keeps the fixture's changeset-owner auth context.
    await ChangesetService.close(changeset_id)
    after = await _properties(client, id)
    assert after['status'] == 'hidden'
    assert after['comments'] == before['comments']
    assert not notify.called


async def test_manual_close_comments_and_skip_closed(
    client: AsyncClient, changeset_id, monkeypatch
):
    ids = [await _note(client) for _ in range(3)]
    r = await client.post(f'/api/0.6/notes/{ids[2]}/close')
    assert r.is_success, r.text
    before = await _properties(client, ids[2])
    notified = []

    async def notify(note, comment):
        # A different request sees committed state before notification begins.
        props = await _properties(client, note['id'])
        assert props['status'] == 'closed'
        assert comment['user']['display_name'] == 'user1'
        notified.append(note['id'])

    monkeypatch.setattr(NoteService, 'notify_activity', notify)
    await ChangesetService.update_tags(
        changeset_id,
        {
            'closes:note': ';'.join(map(str, [*ids, ids[0], 9223372036854775807])),
            'comment': 'default',
            'closes:note:comment': 'global',
            f'closes:note:{ids[0]}:comment': 'individual',
        },
    )
    r = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
    assert r.is_success, r.text
    for id, text in zip(ids[:2], ('individual', 'global'), strict=True):
        props = await _properties(client, id)
        assert props['status'] == 'closed'
        assert props['comments'][-1]['text'] == text
        assert props['comments'][-1]['user'] == 'user1'
    assert (await _properties(client, ids[2]))['comments'] == before['comments']
    assert notified == sorted(ids[:2])


async def test_inactive_close_owner_without_request_auth(
    client: AsyncClient, changeset_id, monkeypatch
):
    id = await _note(client)
    await ChangesetService.update_tags(changeset_id, {'closes:note': str(id)})
    await db_update(
        'changeset',
        {'updated_at': utcnow() - CHANGESET_IDLE_TIMEOUT - timedelta(seconds=1)},
        where={'id': changeset_id},
    )
    notify = AsyncMock()
    monkeypatch.setattr(NoteService, 'notify_activity', notify)
    with auth_context(None):
        await _close_inactive()
    props = await _properties(client, id)
    assert props['status'] == 'closed'
    assert props['comments'][-1]['user'] == 'user1'
    assert not props['comments'][-1]['text']
    assert notify.call_count >= 1


async def test_note_failure_rolls_back_changeset_and_prior_note(
    client: AsyncClient, changeset_id, monkeypatch
):
    ids = sorted([await _note(client), await _note(client)])
    await ChangesetService.update_tags(
        changeset_id, {'closes:note': ';'.join(map(str, ids))}
    )
    original_insert = changeset_notes.db_insert

    async def fail_second(table, values, **kwargs):
        if table == 'note_comment' and values['note_id'] == ids[1]:
            raise RuntimeError('injected second-note failure')
        return await original_insert(table, values, **kwargs)

    monkeypatch.setattr(changeset_notes, 'db_insert', fail_second)
    notify = AsyncMock()
    monkeypatch.setattr(NoteService, 'notify_activity', notify)
    with pytest.raises(RuntimeError, match='injected'):
        await ChangesetService.close(changeset_id)
    assert not notify.called
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None and changeset['closed_at'] is None
    for id in ids:
        props = await _properties(client, id)
        assert props['status'] == 'open'
        assert len(props['comments']) == 1


async def test_size_limit_close_tags_notes(
    client: AsyncClient, changeset_id, monkeypatch
):
    id = await _note(client)
    await ChangesetService.update_tags(
        changeset_id, {'closes:note': str(id), 'comment': 'size limit'}
    )
    monkeypatch.setattr(UserRoleLimits, 'get_changeset_max_size', lambda _roles: 1)
    monkeypatch.setattr(NoteService, 'notify_activity', AsyncMock())
    from app.lib.io.xml_codec import XMLToDict  # noqa: PLC0415

    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/upload',
        content=XMLToDict.unparse({
            'osmChange': {'create': [('node', {'@id': -1, '@lat': 1, '@lon': 1})]}
        }),
    )
    assert r.is_success, r.text
    props = await _properties(client, id)
    assert props['status'] == 'closed'
    assert props['comments'][-1]['text'] == 'size limit'
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None and changeset['closed_at'] is not None
