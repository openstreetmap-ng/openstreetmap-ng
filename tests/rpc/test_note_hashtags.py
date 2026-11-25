from httpx import AsyncClient

from app.models.proto.note_pb2 import (
    AddCommentRequest,
    AddCommentResponse,
    CreateRequest,
    CreateResponse,
    GetCommentsResponse,
    GetRequest,
    GetResponse,
)
from app.models.proto.shared_pb2 import LonLat


async def test_note_current_tags_and_comment_snapshots(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    client.headers['Content-Type'] = 'application/proto'
    response = await client.post(
        '/rpc/note.Service/Create',
        content=CreateRequest(
            location=LonLat(lon=0, lat=0), body='Inspect #first'
        ).SerializeToString(),
    )
    assert response.is_success, response.text
    note_id = CreateResponse.FromString(response.content).id

    response = await client.post(
        '/rpc/note.Service/Get', content=GetRequest(id=note_id).SerializeToString()
    )
    assert response.is_success, response.text
    note = GetResponse.FromString(response.content).note
    assert note.tags == {'hashtags': '#first'}

    for body in ['Checked #second', 'No tag change']:
        response = await client.post(
            '/rpc/note.Service/AddComment',
            content=AddCommentRequest(
                id=note_id, event='commented', body=body
            ).SerializeToString(),
        )
        assert response.is_success, response.text

    result = AddCommentResponse.FromString(response.content)
    assert result.note.tags == {'hashtags': '#second'}
    assert '#first' in result.note.header.body_rich
    assert '#second' not in result.note.header.body_rich
    changed, unchanged = result.comments.comments
    assert changed.HasField('tag_snapshot')
    assert changed.tag_snapshot.tags == {'hashtags': '#second'}
    assert not unchanged.HasField('tag_snapshot')


def test_empty_note_tag_snapshot_preserves_presence():
    comment = GetCommentsResponse.Comment(
        tag_snapshot=GetCommentsResponse.Comment.TagSnapshot(tags={})
    )
    decoded = GetCommentsResponse.Comment.FromString(comment.SerializeToString())
    assert decoded.HasField('tag_snapshot')
    assert not decoded.tag_snapshot.tags
    assert not GetCommentsResponse.Comment().HasField('tag_snapshot')
