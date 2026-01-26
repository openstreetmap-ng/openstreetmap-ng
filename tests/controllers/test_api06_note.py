from datetime import datetime
from random import uniform

import pytest
from annotated_types import Len
from httpx import AsyncClient
from pydantic import PositiveInt
from starlette import status

from app.lib.xmltodict import XMLToDict
from speedup import buffered_randbytes
from tests.utils.assert_model import assert_model


async def test_note_create_xml(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes',
        params={'lon': 0, 'lat': 0, 'text': test_note_create_xml.__qualname__},
    )
    assert r.is_success, r.text
    note: dict = XMLToDict.parse(r.content)['osm']['note'][0]
    comments = note['comments']['comment']

    assert_model(
        note,
        {
            '@lat': 0.0,
            '@lon': 0.0,
            'id': PositiveInt,
            'status': 'open',
            'url': str,
            'comment_url': str,
            'close_url': str,
        },
    )
    assert len(comments) == 1
    assert_model(
        comments[0],
        {
            'user': 'user1',
            'action': 'opened',
            'text': test_note_create_xml.__qualname__,
        },
    )


async def test_note_create_json(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': test_note_create_json.__qualname__},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert_model(props, {'status': 'open', 'comments': Len(1, 1)})
    assert_model(
        props['comments'][0],
        {
            'user': 'user1',
            'action': 'opened',
            'text': test_note_create_json.__qualname__,
        },
    )


async def test_note_create_gpx(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes.gpx',
        params={'lon': 0, 'lat': 0, 'text': test_note_create_gpx.__qualname__},
    )
    assert r.is_success, r.text
    waypoint: dict = XMLToDict.parse(r.content)['gpx']['wpt']

    assert_model(
        waypoint,
        {
            '@lat': 0.0,
            '@lon': 0.0,
            'time': datetime,
            'name': str,
            'link': dict,
            'desc': str,
            'extensions': dict,
        },
    )


async def test_note_create_anonymous(client: AsyncClient):
    r = await client.post(
        '/api/0.6/notes.json',
        json={'lon': 0, 'lat': 0, 'text': test_note_create_anonymous.__qualname__},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert_model(props, {'status': 'open', 'comments': Len(1, 1)})
    assert_model(
        props['comments'][0],
        {
            'action': 'opened',
            'text': test_note_create_anonymous.__qualname__,
        },
    )
    assert 'user' not in props['comments'][0]


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

    assert_model(props, {'status': 'open', 'comments': Len(1, 1)})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'opened',
            'text': test_note_crud.__qualname__,
        },
    )

    # Step 2: Read the note
    r = await client.get(f'/api/0.6/notes/{note_id}.json')
    assert r.is_success, r.text
    props = r.json()['properties']
    assert_model(props, {'id': note_id})

    # Step 3: Comment on the note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/comment.json',
        params={'text': 'Adding a comment'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert_model(props, {'status': 'open', 'comments': Len(2, 2)})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'commented',
            'text': 'Adding a comment',
        },
    )

    # Step 4: Close the note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/close.json',
        params={'text': 'Closing note'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert_model(props, {'status': 'closed', 'comments': Len(3, 3), 'closed_at': str})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'closed',
            'text': 'Closing note',
        },
    )

    # Step 5: Reopen the note
    r = await client.post(
        f'/api/0.6/notes/{note_id}/reopen.json',
        params={'text': 'Reopening note'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    assert_model(props, {'status': 'open', 'comments': Len(4, 4)})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'reopened',
            'text': 'Reopening note',
        },
    )
    assert 'closed_at' not in props

    # Step 6: Hide the note (requires moderator privileges)
    client.headers['Authorization'] = 'User moderator'
    r = await client.delete(
        f'/api/0.6/notes/{note_id}.json',
        params={'text': 'Hiding inappropriate note'},
    )
    assert r.is_success, r.text
    props = r.json()['properties']

    # Check that comments history is preserved and hide action is recorded
    assert_model(props, {'status': 'hidden', 'comments': Len(5, 5)})
    assert_model(
        props['comments'][-1],
        {
            'user': 'moderator',
            'action': 'hidden',
            'text': 'Hiding inappropriate note',
        },
    )

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
    lon = round(uniform(-179, 179), 7)
    lat = round(uniform(-89, 89), 7)
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
    props = r.json()['features'][0]['properties']

    # Verify that note is found
    assert_model(props, {'status': 'open', 'comments': Len(1, 1)})
    assert_model(props['comments'][0], {'text': test_note_query_by_bbox.__qualname__})


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
    props = r.json()['features'][0]['properties']

    # Verify that note is found
    assert_model(props, {'status': 'open', 'comments': Len(1, 1)})
    assert_model(props['comments'][0], {'text': text})


async def test_invalid_note_id(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Try to access a non-existent note
    r = await client.get('/api/0.6/notes/0.json')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text

    # Try to comment on non-existent note
    r = await client.post(
        '/api/0.6/notes/0/comment.json',
        params={'text': 'Comment on invalid note'},
    )
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
