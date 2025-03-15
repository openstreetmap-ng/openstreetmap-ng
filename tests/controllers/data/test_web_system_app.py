from httpx import AsyncClient, Response
from starlette import status

from app.models.db.oauth2_application import (
    SYSTEM_APP_ID_CLIENT_ID,
    SYSTEM_APP_RAPID_CLIENT_ID,
    SYSTEM_APP_WEB_CLIENT_ID,
)
from app.models.types import ClientId


async def test_create_access_token(client: AsyncClient):
    async def call_create_access_token(client_id: ClientId) -> Response:
        return await client.post('/api/web/system-app/create-access-token', data={'client_id': client_id})

    r = await call_create_access_token(SYSTEM_APP_ID_CLIENT_ID)
    assert r.status_code == status.HTTP_401_UNAUTHORIZED

    client.headers['Authorization'] = 'User user1'

    r = await call_create_access_token(SYSTEM_APP_ID_CLIENT_ID)
    assert r.status_code == status.HTTP_200_OK
    assert set(r.json().keys()) == {'access_token'}

    r = await call_create_access_token(SYSTEM_APP_RAPID_CLIENT_ID)
    assert r.status_code == status.HTTP_200_OK

    r = await call_create_access_token(SYSTEM_APP_WEB_CLIENT_ID)
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
