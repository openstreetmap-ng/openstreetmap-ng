from httpx import AsyncClient
from starlette import status


async def test_edit_help_redirects_authenticated_users_to_walkthrough(
    client: AsyncClient,
):
    client.headers['Authorization'] = 'User user1'

    r = await client.get('/?edit_help=1', follow_redirects=False)

    assert r.status_code == status.HTTP_303_SEE_OTHER, r.text
    assert r.headers['Location'] == '/edit#walkthrough=true'


async def test_edit_help_does_not_redirect_anonymous_users(client: AsyncClient):
    r = await client.get('/?edit_help=1', follow_redirects=False)

    assert r.is_success, r.text
