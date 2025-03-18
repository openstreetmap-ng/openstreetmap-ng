import random

import pytest
from httpx import AsyncClient
from starlette import status

from app.lib.buffered_random import buffered_randbytes
from app.lib.xmltodict import XMLToDict
from app.limits import GEO_COORDINATE_PRECISION


async def test_note_create_xml(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes',
        params={'lon': 0, 'lat': 0, 'text': test_note_create_xml.__qualname__},
    )
    assert r.is_success, r.text

    note: dict = XMLToDict.parse(r.content)['osm']['note'][0]  # type: ignore
    assert note['@lat'] == 0
    assert note['@lon'] == 0
    assert 'id' in note
    assert 'url' in note
    assert 'comment_url' in note
    assert 'close_url' in note
    assert note['status'] == 'open'

    comments = note['comments']['comment']
    assert len(comments) == 1
    assert comments[0]['user'] == 'user1'
    assert comments[0]['action'] == 'opened'
    assert comments[0]['text'] == test_note_create_xml.__qualname__


async def test_note_create_json(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': test_note_create_json.__qualname__},
    )
    assert r.is_success, r.text

    data = r.json()
    props = data['properties']
    assert props['status'] == 'open'
    assert len(props['comments']) == 1
    assert props['comments'][0]['user'] == 'user1'
    assert props['comments'][0]['action'] == 'opened'
    assert props['comments'][0]['text'] == test_note_create_json.__qualname__


async def test_note_create_gpx(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes.gpx',
        params={'lon': 0, 'lat': 0, 'text': test_note_create_gpx.__qualname__},
    )
    assert r.is_success, r.text

    waypoint: dict = XMLToDict.parse(r.content)['gpx']['wpt'][0]  # type: ignore
    assert waypoint['@lat'] == 0
    assert waypoint['@lon'] == 0
    assert 'name' in waypoint
    assert 'desc' in waypoint


async def test_note_create_anonymous(client: AsyncClient):
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': test_note_create_anonymous.__qualname__},
    )
    assert r.is_success, r.text

    data = r.json()
    props = data['properties']
    assert props['status'] == 'open'
    assert len(props['comments']) == 1
    assert 'user' not in props['comments'][0]
    assert props['comments'][0]['action'] == 'opened'
    assert props['comments'][0]['text'] == test_note_create_anonymous.__qualname__


async def test_note_crud(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Step 1: Create a note
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': test_note_crud.__qualname__},
    )
    assert r.is_success, r.text
    props = r.json()['properties']
    note_id = props['id']

    assert props['status'] == 'open'
    assert len(props['comments']) == 1
    assert props['comments'][0]['user'] == 'user1'
    assert props['comments'][0]['action'] == 'opened'
    assert props['comments'][0]['text'] == test_note_crud.__qualname__

    # Step 2: Read the note
    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.is_success, r.text
    assert r.json()['properties']['id'] == note_id

    # Step 3: Comment on the note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/comment.json',
        params={'text': 'Adding a comment'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert props['status'] == 'open'
    assert len(props['comments']) == 2
    assert props['comments'][1]['user'] == 'user1'
    assert props['comments'][1]['action'] == 'commented'
    assert props['comments'][1]['text'] == 'Adding a comment'

    # Step 4: Close the note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/close.json',
        params={'text': 'Closing note'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert props['status'] == 'closed'
    assert len(props['comments']) == 3
    assert props['comments'][2]['user'] == 'user1'
    assert props['comments'][2]['action'] == 'closed'
    assert props['comments'][2]['text'] == 'Closing note'
    assert 'date_closed' in props

    # Step 5: Reopen the note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/reopen.json',
        params={'text': 'Reopening note'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert props['status'] == 'open'
    assert len(props['comments']) == 4
    assert props['comments'][3]['user'] == 'user1'
    assert props['comments'][3]['action'] == 'reopened'
    assert props['comments'][3]['text'] == 'Reopening note'
    assert 'date_closed' not in props

    # Step 6: Hide the note (requires moderator privileges)
    client.headers['Authorization'] = 'User moderator'
    r = await client.delete(
        f'/api/0.6/notes/{note_id}.json',
        params={'text': 'Hiding inappropriate note'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    # Check that comments history is preserved and hide action is recorded
    assert len(props['comments']) == 5
    assert props['comments'][4]['user'] == 'moderator'
    assert props['comments'][4]['action'] == 'hidden'
    assert props['comments'][4]['text'] == 'Hiding inappropriate note'

    # Step 7: Verify hidden note is not accessible to regular users
    client.headers['Authorization'] = 'User user1'
    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text


@pytest.mark.parametrize(
    'input_data',
    [
        {'lon': 181, 'lat': 0, 'text': 'Invalid longitude'},
        {'lon': 0, 'lat': 91, 'text': 'Invalid latitude'},
        {'lon': 0, 'lat': 0, 'text': ''},
    ],
)
async def test_note_bad_input(client: AsyncClient, input_data):
    r = await client.post('/api/0.6/notes.json', json=input_data)
    assert r.is_client_error, r.text


async def test_note_query_by_bbox(client: AsyncClient):
    # Create a note at a specific location
    lon = round(random.uniform(-179, 179), GEO_COORDINATE_PRECISION)
    lat = round(random.uniform(-89, 89), GEO_COORDINATE_PRECISION)
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': lon, 'lat': lat, 'text': test_note_query_by_bbox.__qualname__},
    )
    assert r.is_success, r.text

    # Query notes within bbox
    r = await client.get(
        '/api/0.6/notes.json',
        params={
            'bbox': f'{lon},{lat},{lon},{lat}',
            'closed': -1,  # Open notes
        },
    )
    assert r.is_success, r.text

    # Verify that note is found
    props = r.json()['features'][0]['properties']
    assert len(props['comments']) == 1
    assert props['comments'][0]['text'] == test_note_query_by_bbox.__qualname__


async def test_note_search(client: AsyncClient):
    # Create a note with unique text for searching
    search_text = buffered_randbytes(7).hex()
    text = f'{test_note_search.__qualname__} {search_text}'
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': text},
    )
    assert r.is_success, r.text

    # Search by text
    r = await client.get(
        '/api/0.6/notes/search.json',
        params={
            'q': search_text,
            'closed': -1,  # Open notes
        },
    )
    assert r.is_success, r.text

    # Verify that note is found
    props = r.json()['features'][0]['properties']
    assert len(props['comments']) == 1
    assert props['comments'][0]['text'] == text


async def test_invalid_note_id(client: AsyncClient):
    # Try to access a non-existent note
    r = await client.get('/api/0.6/notes/0.json')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text

    # Try to comment on non-existent note
    r = await client.post(
        '/api/0.6/notes/0/comment.json',
        params={'text': 'Comment on invalid note'},
    )
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
