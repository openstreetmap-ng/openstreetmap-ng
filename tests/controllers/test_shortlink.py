import pytest
from httpx import AsyncClient
from starlette import status


@pytest.mark.parametrize(
    ('path', 'expected_redirect'),
    [
        ('/go/x2iS95--', '/#map=9%2F39.59267%2F31.80267'),
    ],
)
async def test_shortlink(client: AsyncClient, path, expected_redirect):
    r = await client.get(path, follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == expected_redirect


async def test_shortlink_not_found(client: AsyncClient):
    r = await client.get('/go/$$$', follow_redirects=False)
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.text
