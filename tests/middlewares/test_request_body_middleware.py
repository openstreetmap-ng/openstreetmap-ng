import gzip
import json

from httpx import AsyncClient


async def test_gzipped_request(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    note_payload = {'lon': 0, 'lat': 0, 'text': 'gzipped note'}
    payload_compressed = gzip.compress(bytes(json.dumps(note_payload), 'utf-8'))
    # create note
    r = await client.post(
        '/api/0.6/notes.json',
        content=payload_compressed,
        headers={'Content-Encoding': 'gzip'},
    )
    assert r.is_success, r.text
    props: dict = r.json()['properties']
    comments: list[dict] = props['comments']

    assert props['status'] == 'open'
    assert len(comments) == 1

    assert comments[-1]['user'] == 'user1'
    assert comments[-1]['action'] == 'opened'
    assert comments[-1]['text'] == 'gzipped note'
