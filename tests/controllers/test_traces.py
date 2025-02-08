from httpx import AsyncClient


async def test_legacy_personal_details(client: AsyncClient):
    r = await client.get('/user/Zaczero/traces/152', follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == '/trace/152'
