from httpx import AsyncClient
from starlette import status


async def test_shortlink(client: AsyncClient):
    r = await client.get('/go/x2iS95--', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == '/#map=9%2F39.59267%2F31.80267'


async def test_shortlink_not_found(client: AsyncClient):
    r = await client.get('/go/$$$', follow_redirects=False)
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
