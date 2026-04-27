from httpx import AsyncClient
from starlette import status

from app.queries.user_profile_query import UserProfileQuery
from app.queries.user_query import UserQuery


async def test_update_description_roundtrip(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    user = await UserQuery.find_by_display_name('user1')  # type: ignore
    assert user is not None
    user_id = user['id']

    # Set description
    r = await client.post(
        '/api/web/settings/description', data={'description': 'Hello world'}
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    assert profile['description'] == 'Hello world'
    assert profile['description_rich_hash'] is not None
    assert profile['description_rich'] == '<p>Hello world</p>\n'  # type: ignore

    # Clear description
    r = await client.post('/api/web/settings/description', data={'description': ''})
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    assert profile['description'] is None
    assert profile['description_rich_hash'] is None


async def test_update_socials_roundtrip(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    user = await UserQuery.find_by_display_name('user1')  # type: ignore
    assert user is not None
    user_id = user['id']

    # Set two socials: one templated (github), one URL (signal, auto-upgrades to https)
    r = await client.post(
        '/api/web/settings/socials',
        data={
            'service': ['github', 'signal'],
            'value': ['octocat', 'http://example.com/group'],
        },
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    socials = [(s.service, s.value) for s in profile['socials']]
    assert socials == [
        ('github', 'octocat'),
        ('signal', 'https://example.com/group'),
    ]

    # Clear again
    r = await client.post('/api/web/settings/socials', data={})
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    assert profile['socials'] == []


async def test_update_avatar_with_invalid_image_returns_readable_validation_error(
    client: AsyncClient,
):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/web/settings/avatar',
        data={'avatar_type': 'custom'},
        files={'avatar_file': ('bad.txt', b'not-an-image', 'text/plain')},
    )

    assert r.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, r.text
    assert r.json() == {'detail': 'Image is not readable'}
