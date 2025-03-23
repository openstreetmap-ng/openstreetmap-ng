import pytest
from httpx import AsyncClient
from starlette import status

from app.queries.user_query import UserQuery


@pytest.mark.parametrize('path', ['', '/test', '/test?abc=def'])
async def test_user_permalink(client: AsyncClient, path):
    client.headers['Authorization'] = 'User user1'
    user_id = (await UserQuery.find_one_by_display_name('user1'))['id']  # type: ignore

    # Test that user id permalink redirects to username permalink
    r = await client.get(f'/user-id/{user_id}{path}', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == f'/user/user1{path}'


async def test_user_permalink_not_found(client: AsyncClient):
    r = await client.get('/user-id/0', follow_redirects=False)
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text


async def test_signup_redirect_when_authenticated(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.get('/signup', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == '/'


@pytest.mark.parametrize(
    ('old_path', 'new_path'),
    [
        ('/user/new', '/signup'),
        ('/user/forgot-password', '/reset-password'),
        ('/user/reset-password?token=abc123', '/reset-password?token=abc123'),
    ],
)
async def test_legacy_redirects(client: AsyncClient, old_path, new_path):
    r = await client.get(old_path, follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == new_path
