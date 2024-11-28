from httpx import AsyncClient
from starlette import status

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


async def test_note_with_xml(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create note
    r = await client.post(
        '/api/0.6/notes',
        params={'lon': 0, 'lat': 0, 'text': test_note_with_xml.__qualname__},
    )
    assert r.is_success, r.text
    props: dict = XMLToDict.parse(r.content)['osm']['note'][0]
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
    assert comments[-1]['user_url'] == f'{APP_URL}/user-id/{comments[-1]['uid']}'
    assert comments[-1]['action'] == 'opened'
    assert comments[-1]['text'] == test_note_with_xml.__qualname__
    assert comments[-1]['html'] == f'<p>{test_note_with_xml.__qualname__}</p>'


async def test_note_hide_unhide(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # create note
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': test_note_hide_unhide.__qualname__},
    )
    assert r.is_success, r.text
    props: dict = r.json()['properties']
    note_id: int = props['id']

    # fail to hide
    r = await client.delete(
        f'/api/0.6/notes/{note_id}.json',
        params={'text': 'hide'},
    )
    assert r.status_code == status.HTTP_403_FORBIDDEN, r.text

    # hide
    client.headers['Authorization'] = 'User moderator'
    r = await client.delete(
        f'/api/0.6/notes/{note_id}.json',
        params={'text': 'hide'},
    )
    assert r.is_success, r.text

    # fail to get note
    client.headers['Authorization'] = 'User user1'
    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text

    # unhide
    client.headers['Authorization'] = 'User moderator'
    r = await client.post(
        f'/api/0.6/notes/{note_id}/reopen.json',
        params={'text': 'unhide'},
    )
    assert r.is_success, r.text

    # get note
    client.headers['Authorization'] = 'User user1'
    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.is_success, r.text
