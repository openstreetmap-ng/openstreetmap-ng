from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.config import CHANGESET_IDLE_TIMEOUT
from app.db import db_update
from app.lib.io.xml_codec import XMLToDict
from app.lib.time.date_utils import utcnow
from app.queries.changeset_query import ChangesetQuery
from app.services.changeset_service import ChangesetService


@pytest.mark.parametrize('automatic', [False, True])
@pytest.mark.parametrize('with_comments', [False, True])
async def test_changeset_closes_notes(client: AsyncClient, automatic, with_comments):
    client.headers['Authorization'] = 'User user1'
    ids = []
    for _ in range(4):
        response = await client.post(
            '/api/0.6/notes.json',
            json={'lon': 0, 'lat': 0, 'text': 'Please check this place'},
        )
        assert response.is_success, response.text
        ids.append(response.json()['properties']['id'])

    response = await client.post(
        f'/api/0.6/notes/{ids[2]}/close.json', params={'text': 'Already handled'}
    )
    assert response.is_success, response.text

    client.headers['Authorization'] = 'User user2'
    tags = {
        'closes:note': ';'.join(map(str, [*ids, ids[0], 9223372036854775807]))
        + ';invalid',
        'comment': 'Changeset description',
        'closes:note:comment': 'Mapped on site',
        f'closes:note:{ids[1]}:comment': 'Address verified',
    }
    if not with_comments:
        tags = {'closes:note': tags['closes:note']}
    response = await client.put(
        '/api/0.6/changeset/create',
        content=XMLToDict.unparse({
            'osm': {'changeset': {'tag': [{'@k': k, '@v': v} for k, v in tags.items()]}}
        }),
    )
    assert response.is_success, response.text
    changeset_id = int(response.text)

    # Uploading the tags alone must leave the notes open.
    response = await client.get(f'/api/0.6/notes/{ids[0]}.json')
    assert response.json()['properties']['status'] == 'open'

    if automatic:
        old = utcnow() - CHANGESET_IDLE_TIMEOUT - timedelta(seconds=1)
        await db_update(
            'changeset',
            {'created_at': old, 'updated_at': old},
            where={'id': changeset_id},
        )
        await ChangesetService.force_process()
        await ChangesetService.force_process()
    else:
        response = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
        assert response.is_success, response.text
        # A denied repeat must not add duplicate note comments.
        response = await client.put(f'/api/0.6/changeset/{changeset_id}/close')
        assert response.status_code == 409, response.text

    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None and changeset['closed_at'] is not None
    expected = (
        ['Mapped on site', 'Address verified', 'Already handled', 'Mapped on site']
        if with_comments
        else ['', '', 'Already handled', '']
    )
    for note_id, text in zip(ids, expected, strict=True):
        response = await client.get(f'/api/0.6/notes/{note_id}.json')
        assert response.is_success, response.text
        props = response.json()['properties']
        assert props['status'] == 'closed'
        assert len(props['comments']) == 2
        closing = props['comments'][-1]
        assert closing['action'] == 'closed'
        assert closing.get('text', '') == text
        assert closing['user'] == ('user1' if note_id == ids[2] else 'user2')
