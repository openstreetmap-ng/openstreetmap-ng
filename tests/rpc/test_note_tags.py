import pytest
from httpx import AsyncClient

from app.models.proto.note_pb2 import (
    AddCommentRequest,
    AddCommentResponse,
    CreateRequest,
    CreateResponse,
    GetRequest,
    GetResponse,
)
from app.models.proto.shared_pb2 import LonLat


async def _create(client):
    client.headers['Authorization'] = 'User user1'
    r = await client.post(
        '/rpc/note.Service/Create',
        headers={'Content-Type': 'application/proto'},
        content=CreateRequest(
            location=LonLat(lon=0, lat=0), body='Test #old'
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    return CreateResponse.FromString(r.content).id


async def _comment(client, request):
    return await client.post(
        '/rpc/note.Service/AddComment',
        headers={'Content-Type': 'application/proto'},
        content=request.SerializeToString(),
    )


async def test_note_tag_replacement_clear_and_legacy_compatibility(client: AsyncClient):
    id = await _create(client)
    tags = {'source': 'survey', 'hashtags': '#new'}
    r = await _comment(
        client,
        AddCommentRequest(
            id=id,
            event='commented',
            body='Literal #context',
            tag_update=AddCommentRequest.TagUpdate(tags=tags),
        ),
    )
    assert r.is_success, r.text
    result = AddCommentResponse.FromString(r.content)
    assert dict(result.note.tags) == tags
    assert dict(result.comments.comments[-1].tag_snapshot.tags) == tags
    assert '#context' in result.comments.comments[-1].body_rich

    r = await _comment(
        client,
        AddCommentRequest(
            id=id,
            event='commented',
            body='No tag change',
        ),
    )
    assert r.is_success, r.text
    result = AddCommentResponse.FromString(r.content)
    assert dict(result.note.tags) == tags
    assert not result.comments.comments[-1].HasField('tag_snapshot')

    r = await _comment(
        client,
        AddCommentRequest(
            id=id,
            event='commented',
            tag_update=AddCommentRequest.TagUpdate(tags={}),
        ),
    )
    assert r.is_success, r.text
    result = AddCommentResponse.FromString(r.content)
    assert dict(result.note.tags) == {}
    assert result.comments.comments[-1].HasField('tag_snapshot')
    assert dict(result.comments.comments[-1].tag_snapshot.tags) == {}
    assert dict(result.comments.comments[0].tag_snapshot.tags) == tags

    r = await _comment(
        client, AddCommentRequest(id=id, event='commented', body='Legacy #restored')
    )
    assert r.is_success, r.text
    assert dict(AddCommentResponse.FromString(r.content).note.tags) == {
        'hashtags': '#restored'
    }


@pytest.mark.parametrize(
    'tags', [{'': 'bad'}, {'source': 'x' * 256}, {'source': '\x00'}]
)
async def test_invalid_note_tags_are_rejected_without_mutation(
    client: AsyncClient, tags
):
    id = await _create(client)
    r = await _comment(
        client,
        AddCommentRequest(
            id=id,
            event='commented',
            tag_update=AddCommentRequest.TagUpdate(tags=tags),
        ),
    )
    assert r.status_code == 400, r.text
    r = await client.post(
        '/rpc/note.Service/Get',
        headers={'Content-Type': 'application/proto'},
        content=GetRequest(id=id).SerializeToString(),
    )
    assert r.is_success, r.text
    assert dict(GetResponse.FromString(r.content).note.tags) == {'hashtags': '#old'}


async def test_anonymous_user_cannot_replace_note_tags(client: AsyncClient):
    id = await _create(client)
    client.headers.pop('Authorization')
    r = await _comment(
        client,
        AddCommentRequest(
            id=id,
            event='commented',
            tag_update=AddCommentRequest.TagUpdate(tags={}),
        ),
    )
    assert r.status_code in (401, 403), r.text
