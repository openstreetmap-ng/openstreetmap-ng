import pytest
from httpx import AsyncClient
from starlette import status


@pytest.mark.parametrize('path', ['', '/test', '/test?abc=def'])
async def test_user_permalink(client: AsyncClient, path: str):
    client.headers['Authorization'] = 'User user1'

    # get user details
    r = await client.get('/api/0.6/user/details.json')
    assert r.is_success, r.text
    user: dict = r.json()['user']

    user_id = user['id']

    r = await client.get(f'/user-id/{user_id}{path}', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == f'/user/user1{path}'


async def test_user_permalink_not_found(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.get('/user-id/123123123123123123', follow_redirects=False)
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
    assert r.json()['detail'] == 'User 123123123123123123 not found'
