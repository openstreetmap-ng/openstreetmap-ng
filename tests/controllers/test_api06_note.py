from httpx import AsyncClient

from app.config import API_URL, APP_URL
from app.lib.xmltodict import XMLToDict


async def test_note_crud(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create note
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': 'create'},
    )
    assert r.is_success, r.text
    props: dict = r.json()['properties']
    comments: list[dict] = props['comments']
    note_id: int = props['id']

    assert props['status'] == 'open'
    assert len(comments) == 1
    assert comments[-1]['user'] == 'user1'
    assert comments[-1]['action'] == 'opened'
    assert comments[-1]['text'] == 'create'

    # read note
    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.is_success, r.text
    assert r.json()['properties'] == props

    # comment note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/comment.json',
        params={'text': 'comment'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']
    comments = props['comments']

    assert props['status'] == 'open'
    assert len(comments) == 2
    assert comments[-1]['user'] == 'user1'
    assert comments[-1]['action'] == 'commented'
    assert comments[-1]['text'] == 'comment'

    # resolve note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/close.json',
        params={'text': 'resolve'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']
    comments = props['comments']

    assert props['status'] == 'closed'
    assert len(comments) == 3
    assert comments[-1]['user'] == 'user1'
    assert comments[-1]['action'] == 'closed'
    assert comments[-1]['text'] == 'resolve'


async def test_note_xml(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create note
    r = await client.post(
        '/api/0.6/notes',
        params={'lon': 0, 'lat': 0, 'text': test_note_xml.__qualname__},
    )
    assert r.is_success, r.text
    props: dict = XMLToDict.parse(r.content)['osm']['note']
    assert props['@lon'] == 0
    assert props['@lat'] == 0
    assert int(props['id']) > 0
    assert props['url'] == f'{API_URL}/api/0.6/notes/{props['id']}'
    assert 'reopen_url' not in props
    assert props['comment_url'] == f'{API_URL}/api/0.6/notes/{props['id']}/comment'
    assert props['close_url'] == f'{API_URL}/api/0.6/notes/{props['id']}/close'
    assert 'date_created' in props
    assert 'date_closed' not in props
    assert props['status'] == 'open'
    comments: list[dict] = props['comments']['comment']
    assert len(comments) == 1
    assert 'date' in comments[-1]
    assert comments[-1]['user'] == 'user1'
    assert comments[-1]['user_url'] == f'{APP_URL}/user/permalink/{comments[-1]['uid']}'
    assert comments[-1]['action'] == 'opened'
    assert comments[-1]['text'] == test_note_xml.__qualname__
    assert comments[-1]['html'] == f'<p>{test_note_xml.__qualname__}</p>'
