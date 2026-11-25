from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.db import db_fetchone
from app.models.db.note import Note
from app.models.db.note_comment import note_comments_resolve_rich_text
from app.models.proto.note_pb2 import (
    AddCommentRequest,
    AddCommentResponse,
    CreateRequest,
    CreateResponse,
    GetCommentsResponse,
    Tags,
)
from app.models.proto.shared_pb2 import LonLat
from app.queries.nominatim_query import NominatimQuery
from app.queries.note_query import NoteCommentQuery


@pytest.fixture(autouse=True)
def _local_geocoding(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(NominatimQuery, 'reverse', AsyncMock(return_value=None))


async def test_legacy_api_hashtags_roundtrip_without_changing_stored_text(
    client: AsyncClient,
):
    client.headers['Authorization'] = 'User user1'
    response = await client.post(
        '/api/0.6/notes.json',
        json={
            'lon': 0,
            'lat': 0,
            'text': 'Needs survey #survey #osm-ng',
        },
    )
    assert response.is_success, response.text
    props = response.json()['properties']
    note_id = props['id']
    assert props['comments'][0]['text'] == 'Needs survey\n#survey #osm-ng'
    assert '#survey' in props['comments'][0]['html']
    header = await NoteCommentQuery.find_header(note_id)
    assert header is not None
    assert header['body'] == 'Needs survey'
    assert header['tags'] == {'hashtags': '#survey;#osm-ng'}

    # Reading twice must not store legacy rendered text in the web cache.
    response = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert response.is_success, response.text
    assert (
        response.json()['properties']['comments'][0]['text']
        == props['comments'][0]['text']
    )
    stored_header = await NoteCommentQuery.find_header(note_id)
    assert stored_header is not None
    await note_comments_resolve_rich_text([stored_header])
    body_rich = stored_header.get('body_rich')
    assert body_rich is not None and '#survey' not in body_rich
    response = await client.post(
        f'/api/0.6/notes/{note_id}/comment.json', params={'text': 'Checked'}
    )
    assert response.is_success, response.text
    note = await db_fetchone(Note, t'SELECT * FROM note WHERE id = {note_id}')
    assert note is not None and note['tags'] == {'hashtags': '#survey;#osm-ng'}

    response = await client.post(
        f'/api/0.6/notes/{note_id}/close.json', params={'text': '#solved'}
    )
    assert response.is_success, response.text
    comments = response.json()['properties']['comments']
    assert comments[0]['text'] == 'Needs survey\n#survey #osm-ng'
    assert comments[-1]['text'] == '#solved'
    note = await db_fetchone(Note, t'SELECT * FROM note WHERE id = {note_id}')
    assert note is not None and note['tags'] == {'hashtags': '#solved'}


async def test_rpc_tag_presence_and_validation(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    headers = {'Content-Type': 'application/proto'}
    response = await client.post(
        '/rpc/note.Service/Create',
        headers=headers,
        content=CreateRequest(
            location=LonLat(lon=0, lat=0),
            body='RPC note',
            tags=Tags(values={'hashtags': '#survey', 'source': 'test'}),
        ).SerializeToString(),
    )
    assert response.is_success, response.text
    note_id = CreateResponse.FromString(response.content).id
    response = await client.post(
        '/rpc/note.Service/AddComment',
        headers=headers,
        content=AddCommentRequest(
            id=note_id,
            event=GetCommentsResponse.Comment.commented,
            body='No tag change',
        ).SerializeToString(),
    )
    assert response.is_success, response.text
    result = AddCommentResponse.FromString(response.content)
    assert dict(result.note.tags) == {'hashtags': '#survey', 'source': 'test'}
    assert not result.comments.comments[-1].HasField('tags')

    response = await client.post(
        '/rpc/note.Service/AddComment',
        headers=headers,
        content=AddCommentRequest(
            id=note_id,
            event=GetCommentsResponse.Comment.commented,
            body='',
            tags=Tags(),
        ).SerializeToString(),
    )
    assert response.is_success, response.text
    result = AddCommentResponse.FromString(response.content)
    assert not result.note.tags
    assert dict(result.note.header.tags.values) == {
        'hashtags': '#survey',
        'source': 'test',
    }
    assert result.comments.comments[-1].HasField('tags')

    response = await client.post(
        '/rpc/note.Service/AddComment',
        headers=headers,
        content=AddCommentRequest(
            id=note_id,
            event=GetCommentsResponse.Comment.commented,
            body='Invalid',
            tags=Tags(values={'hashtags': 'not a hashtag'}),
        ).SerializeToString(),
    )
    assert response.status_code == 400, response.text
