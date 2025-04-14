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
        return await client.post(
            '/api/web/system-app/create-access-token', data={'client_id': client_id}
        )

    # Test unauthenticated access
    r = await call_create_access_token(SYSTEM_APP_ID_CLIENT_ID)
    assert r.status_code == status.HTTP_401_UNAUTHORIZED, r.text

    client.headers['Authorization'] = 'User user1'

    # Test access token creation for iD app (supported)
    r = await call_create_access_token(SYSTEM_APP_ID_CLIENT_ID)
    assert r.is_success, r.text
    assert set(r.json()) == {'access_token'}

    # Test access token creation for Rapid app (supported)
    r = await call_create_access_token(SYSTEM_APP_RAPID_CLIENT_ID)
    assert r.is_success, r.text

    # Test access token creation for Web app (unsupported)
    r = await call_create_access_token(SYSTEM_APP_WEB_CLIENT_ID)
    assert r.is_client_error, r.text
