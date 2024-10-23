from httpx import AsyncClient, Response
from starlette import status


async def test_create_access_token(client: AsyncClient):
    async def call_create_access_token(client_id: str) -> Response:
        return await client.post('/api/web/system-app/create-access-token', data={'client_id': client_id})

    r = await call_create_access_token('SystemApp.id')
    assert r.status_code == status.HTTP_401_UNAUTHORIZED

    client.headers['Authorization'] = 'User user1'

    r = await call_create_access_token('SystemApp.id')
    assert r.status_code == status.HTTP_200_OK
    assert set(r.json().keys()) == {'access_token'}

    r = await call_create_access_token('SystemApp.rapid')
    assert r.status_code == status.HTTP_200_OK

    r = await call_create_access_token('SystemApp.web')
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
