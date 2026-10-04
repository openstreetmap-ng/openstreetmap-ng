from httpx import AsyncClient

from app.models.proto.note_pb2 import CreateRequest, CreateResponse
from app.models.proto.shared_pb2 import LonLat
from app.queries.note_comment_query import NoteCommentQuery


async def _create_note(client: AsyncClient, body: str) -> int:
    r = await client.post(
        '/rpc/note.Service/Create',
        headers={'Content-Type': 'application/proto'},
        content=CreateRequest(
            location=LonLat(lon=0, lat=0),
            body=body,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    return int(CreateResponse.FromString(r.content).id)


async def test_create_appends_osm_ng_hashtag(client: AsyncClient):
    body = test_create_appends_osm_ng_hashtag.__qualname__
    note_id = await _create_note(client, body)

    header = await NoteCommentQuery.find_header(note_id)

    assert header is not None
    assert header['body'] == f'{body}\n#osm-ng'


async def test_create_preserves_existing_osm_ng_hashtag(client: AsyncClient):
    body = f'{test_create_preserves_existing_osm_ng_hashtag.__qualname__}\n#osm-ng'
    note_id = await _create_note(client, body)

    header = await NoteCommentQuery.find_header(note_id)

    assert header is not None
    assert header['body'] == body
