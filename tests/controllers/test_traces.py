import pytest
from httpx import AsyncClient


@pytest.mark.parametrize(
    'suffix',
    ['', '/tag/hiking'],
)
async def test_authenticated_mine_redirect(client: AsyncClient, suffix):
    client.headers['Authorization'] = 'User user1'

    r = await client.get(f'/traces/mine{suffix}', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == f'/user/user1/traces{suffix}'


@pytest.mark.parametrize(
    ('path', 'expected_redirect'),
    [
        ('/user/Zaczero/traces/152', '/trace/152'),
        ('/traces/new', '/trace/upload'),
    ],
)
async def test_legacy_redirects(client: AsyncClient, path, expected_redirect):
    r = await client.get(path, follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == expected_redirect
