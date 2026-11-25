import pytest
from httpx import AsyncClient

from app.db import db, db_fetchrow, db_fetchrows, db_insert, db_update
from app.lib.text.note_hashtags import append_note_hashtags
from app.services import migration_service
from app.services.migration_service import MigrationService


async def _legacy_note(bodies):
    async with db(True) as conn:
        (note_id,) = await db_insert(
            'note',
            {'point': t'ST_SetSRID(ST_MakePoint(0, 0), 4326)'},
            returning='id',
            conn=conn,
        )
        ids = []
        for index, body in enumerate(bodies):
            (comment_id,) = await db_insert(
                'note_comment',
                {
                    'note_id': note_id,
                    'event': 'opened' if index == 0 else 'commented',
                    'body': body,
                    'body_rich_hash': b'cached-before-migration',
                },
                returning='id',
                conn=conn,
            )
            ids.append(comment_id)
    return note_id, ids


async def _comments(note_id):
    return await db_fetchrows(
        t"""
            SELECT id, body, tags, body_rich_hash, event, created_at
            FROM note_comment WHERE note_id = {note_id} ORDER BY id
        """
    )


async def test_backfill_preview_history_and_repeat(client: AsyncClient):
    bodies = ['First #survey', 'Again #survey', 'Plain', 'Checked #جدة']
    note_id, ids = await _legacy_note(bodies)
    before = await _comments(note_id)
    note_before = await db_fetchrow(
        t'SELECT created_at, updated_at, closed_at, hidden_at FROM note WHERE id = {note_id}'
    )
    options = {'before_comment_id': ids[-1], 'start_note_id': note_id}

    preview = await MigrationService.backfill_note_hashtags(**options)
    assert preview['changed_comments'] == 2
    assert preview['changed_notes'] == 1
    assert await _comments(note_id) == before
    assert (await db_fetchrow(t'SELECT tags FROM note WHERE id = {note_id}')) == ({},)

    applied = await MigrationService.backfill_note_hashtags(**options, dry_run=False)
    assert applied['changed_comments'] == 2
    assert applied['next_note_id'] is None
    after = await _comments(note_id)
    assert [row[2] for row in after] == [
        {'hashtags': '#survey'},
        None,
        None,
        {'hashtags': '#جدة'},
    ]
    assert [append_note_hashtags(row[1], row[2]) for row in after] == [
        'First\n#survey',
        'Again #survey',
        'Plain',
        'Checked\n#جدة',
    ]
    assert after[0][3] is None and after[3][3] is None
    assert after[1][3] == before[1][3]
    assert [(row[0], row[4:]) for row in after] == [(row[0], row[4:]) for row in before]
    assert (await db_fetchrow(t'SELECT tags FROM note WHERE id = {note_id}')) == (
        {'hashtags': '#جدة'},
    )
    assert (
        await db_fetchrow(
            t'SELECT created_at, updated_at, closed_at, hidden_at FROM note WHERE id = {note_id}'
        )
        == note_before
    )
    assert await db_fetchrows(
        t"""SELECT id FROM note_comment WHERE id = {ids[0]}
            AND to_tsvector('simple', body || E'\n' || COALESCE(tags -> 'hashtags', ''))
                @@ plainto_tsquery('simple', 'survey')"""
    ) == [(ids[0],)]

    repeat = await MigrationService.backfill_note_hashtags(**options, dry_run=False)
    assert repeat['changed_comments'] == repeat['changed_notes'] == 0
    assert await _comments(note_id) == after

    response = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert response.is_success, response.text
    comments = response.json()['properties']['comments']
    assert [comment['text'] for comment in comments] == [
        'First\n#survey',
        'Again #survey',
        'Plain',
        'Checked\n#جدة',
    ]
    assert '#survey' in comments[0]['html']
    assert '#جدة' not in comments[0]['html']


async def test_backfill_preserves_newer_clear_and_literal_hashtags():
    note_id, ids = await _legacy_note(['Old #survey', 'Clear', 'Literal #untouched'])
    await db_update('note_comment', {'tags': {}}, where={'id': ids[1]})
    result = await MigrationService.backfill_note_hashtags(
        before_comment_id=ids[0], start_note_id=note_id, dry_run=False
    )
    assert result['changed_comments'] == 1
    after = await _comments(note_id)
    assert [row[2] for row in after] == [{'hashtags': '#survey'}, {}, None]
    assert after[-1][1] == 'Literal #untouched'
    assert (await db_fetchrow(t'SELECT tags FROM note WHERE id = {note_id}')) == ({},)


async def test_backfill_batches_and_unsupported_text():
    first, _first_ids = await _legacy_note([
        'https://example.org/#fragment',
        '#' + 'a' * 255,
    ])
    second, second_ids = await _legacy_note(['Second #next'])
    options = {'before_comment_id': second_ids[-1], 'batch_size': 1, 'dry_run': False}
    initial = await _comments(first)
    result = await MigrationService.backfill_note_hashtags(
        **options, start_note_id=first
    )
    assert result['notes_scanned'] == 1
    assert result['changed_comments'] == 0
    assert await _comments(first) == initial
    assert (await _comments(second))[0][2] is None
    result = await MigrationService.backfill_note_hashtags(
        **options, start_note_id=result['next_note_id']
    )
    assert result['changed_comments'] == 1
    assert (await _comments(second))[0][2] == {'hashtags': '#next'}
    final = await MigrationService.backfill_note_hashtags(
        **options, start_note_id=result['next_note_id']
    )
    assert final['notes_scanned'] == 0
    assert final['next_note_id'] is None


async def test_backfill_failed_batch_rolls_back(monkeypatch):
    note_id, ids = await _legacy_note(['First #one', 'Second #two'])
    before = await _comments(note_id)
    calls = 0

    async def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('Synthetic failed write')
        return await db_update(*args, **kwargs)

    monkeypatch.setattr(migration_service, 'db_update', fail_second)
    with pytest.raises(RuntimeError, match='Synthetic failed write'):
        await MigrationService.backfill_note_hashtags(
            before_comment_id=ids[-1], start_note_id=note_id, dry_run=False
        )
    assert calls == 2
    assert await _comments(note_id) == before
    assert (await db_fetchrow(t'SELECT tags FROM note WHERE id = {note_id}')) == ({},)


@pytest.mark.parametrize(
    'kwargs',
    [
        {'before_comment_id': -1},
        {'before_comment_id': 0, 'start_note_id': 0},
        {'before_comment_id': 0, 'batch_size': 0},
    ],
)
async def test_backfill_rejects_invalid_bounds(kwargs):
    with pytest.raises(ValueError, match='migration bounds'):
        await MigrationService.backfill_note_hashtags(**kwargs)
