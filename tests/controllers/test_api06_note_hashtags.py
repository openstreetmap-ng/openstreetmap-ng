from httpx import AsyncClient

from app.lib.auth.context import auth_context
from app.lib.io.xml_codec import XMLToDict
from app.models.types import NoteId
from app.queries.note_query import NoteCommentQuery, NoteQuery


async def test_note_hashtag_snapshots_round_trip(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    response = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': 'Check road #firstsurvey'},
    )
    assert response.is_success, response.text
    note_id = NoteId(response.json()['properties']['id'])

    for text in ['No tag change', 'Checked #secondsurvey', 'Again #secondsurvey']:
        response = await client.post(
            f'/api/0.6/notes/{note_id}/comment.json', params={'text': text}
        )
        assert response.is_success, response.text

    comments = response.json()['properties']['comments']
    assert [comment['text'] for comment in comments] == [
        'Check road\n#firstsurvey',
        'No tag change',
        'Checked\n#secondsurvey',
        'Again #secondsurvey',
    ]
    assert '#firstsurvey' in comments[0]['html']
    assert '#secondsurvey' not in comments[0]['html']
    assert '#secondsurvey' in comments[2]['html']

    with auth_context(None):
        notes = await NoteQuery.find(note_ids=[note_id], limit=1)
    assert notes[0]['tags'] == {'hashtags': '#secondsurvey'}
    stored = await NoteCommentQuery.resolve_comments(notes)
    assert [comment['tags'] for comment in stored] == [
        {'hashtags': '#firstsurvey'},
        None,
        {'hashtags': '#secondsurvey'},
        None,
    ]
    assert stored[0]['body'] == 'Check road'
    assert stored[2]['body'] == 'Checked'

    # The legacy joined query must return comment snapshots, not current tags.
    with auth_context(None):
        feed = await NoteCommentQuery.legacy_find(limit=100)
    history = {comment['id']: comment for comment in feed}
    assert history[stored[0]['id']]['tags'] == {'hashtags': '#firstsurvey'}
    assert history[stored[1]['id']]['tags'] is None


async def test_note_hashtags_remain_searchable(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    hashtag = '#uniquenotehashtagregression'
    response = await client.post(
        '/api/0.6/notes.json', json={'lon': 0, 'lat': 0, 'text': hashtag}
    )
    assert response.is_success, response.text
    props = response.json()['properties']
    assert props['comments'][0]['text'] == hashtag
    assert hashtag in props['comments'][0]['html']
    response = await client.get('/api/0.6/notes/search.json', params={'q': hashtag})
    assert response.is_success, response.text
    assert props['id'] in [
        note['properties']['id'] for note in response.json()['features']
    ]


async def test_note_hashtag_xml_and_url_fragment(client: AsyncClient):
    response = await client.post(
        '/api/0.6/notes',
        params={'lon': 0, 'lat': 0, 'text': 'https://example.org/#place #survey'},
    )
    assert response.is_success, response.text
    note = XMLToDict.parse(response.content)['osm']['note'][0]
    assert (
        note['comments']['comment'][0]['text'] == 'https://example.org/#place\n#survey'
    )


async def test_oversized_hashtags_preserve_original_comment(client: AsyncClient):
    text = '#' + 'a' * 255
    response = await client.post(
        '/api/0.6/notes.json', json={'lon': 0, 'lat': 0, 'text': text}
    )
    assert response.is_success, response.text
    props = response.json()['properties']
    assert props['comments'][0]['text'] == text
    with auth_context(None):
        notes = await NoteQuery.find(note_ids=[NoteId(props['id'])], limit=1)
    assert notes[0]['tags'] == {}
    stored = await NoteCommentQuery.resolve_comments(notes)
    assert stored[0]['body'] == text
    assert stored[0]['tags'] is None
