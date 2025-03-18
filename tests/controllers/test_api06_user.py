from asyncio import TaskGroup

import pytest
from httpx import AsyncClient
from pydantic import NonNegativeInt, PositiveInt
from starlette import status

from app.lib.locale import DEFAULT_LOCALE
from app.queries.user_query import UserQuery
from tests.utils.assert_model import assert_model


async def test_current_user(client: AsyncClient):
    # Test unauthenticated access first
    r = await client.get('/api/0.6/user/details.json')
    assert r.status_code == status.HTTP_401_UNAUTHORIZED, r.text

    # Test authenticated access
    client.headers['Authorization'] = 'User user1'
    r = await client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text
    user: dict = r.json()['user']

    # Verify response structure
    assert_model(
        user,
        {
            'id': PositiveInt,
            'display_name': 'user1',
            'account_created': str,
            'languages': [DEFAULT_LOCALE],
            'roles': [],
            'description': str,
            'contributor_terms': {'agreed': True, 'pd': False},
            'changesets': {'count': NonNegativeInt},
            'traces': {'count': NonNegativeInt},
            'messages': {
                'received': {
                    'count': NonNegativeInt,
                    'unread': NonNegativeInt,
                },
                'sent': {
                    'count': NonNegativeInt,
                },
            },
            'blocks': {
                'received': {
                    'count': NonNegativeInt,
                    'active': NonNegativeInt,
                },
                'issued': {
                    'count': NonNegativeInt,
                    'active': NonNegativeInt,
                },
            },
        },
    )


async def test_get_user_by_id(client: AsyncClient):
    user_id = await UserQuery.find_one_by_display_name('user1')['id']  # type: ignore

    r = await client.get(f'/api/0.6/user/{user_id}.json')
    assert r.is_success, r.text
    user_data = r.json()['user']

    assert_model(user_data, {'id': user_id, 'display_name': 'user1'})


async def test_get_nonexistent_user(client: AsyncClient):
    r = await client.get('/api/0.6/user/0.json')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
    assert 'User 0 not found' in r.text


async def test_get_multiple_users(client: AsyncClient):
    async with TaskGroup() as tg:
        user1_task = tg.create_task(UserQuery.find_one_by_display_name('user1'))  # type: ignore
        user2_task = tg.create_task(UserQuery.find_one_by_display_name('user2'))  # type: ignore
    user1_id = user1_task.result()['id']  # type: ignore
    user2_id = user2_task.result()['id']  # type: ignore

    # Test getting multiple users
    r = await client.get(f'/api/0.6/users.json?users={user1_id},{user2_id}')
    assert r.is_success, r.text
    data = r.json()

    assert len(data['users']) == 2, 'Response must contain exactly two users'

    # Verify both users are in the response with correct data
    users_by_id = {user['id']: user for user in data['users']}
    assert users_by_id[user1_id]['display_name'] == 'user1'
    assert users_by_id[user2_id]['display_name'] == 'user2'


async def test_get_multiple_users_with_nonexistent(client: AsyncClient):
    user_id = await UserQuery.find_one_by_display_name('user1')['id']  # type: ignore

    # Request should succeed but only return the existing user
    r = await client.get(f'/api/0.6/users.json?users={user_id},0')
    assert r.is_success, r.text
    data = r.json()

    assert len(data['users']) == 1
    assert_model(data['users'][0], {'id': user_id, 'display_name': 'user1'})


@pytest.mark.parametrize(
    ('users', 'expected_status'),
    [
        ('abc,def', status.HTTP_400_BAD_REQUEST),  # Non-numeric values
        ('', status.HTTP_400_BAD_REQUEST),  # Empty parameter
    ],
)
async def test_get_multiple_users_invalid_params(client: AsyncClient, users, expected_status):
    r = await client.get(f'/api/0.6/users.json?users={users}')
    assert r.status_code == expected_status, r.text
