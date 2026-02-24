from httpx import AsyncClient

from app.models.proto.settings_pb2 import (
    UpdateDescriptionRequest,
    UpdateSocialsRequest,
)
from app.models.proto.shared_pb2 import UserSocial
from app.models.types import DisplayName
from app.queries.user_profile_query import UserProfileQuery
from app.queries.user_query import UserQuery


async def test_update_description_roundtrip(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    user = await UserQuery.find_by_display_name('user1')  # type: ignore
    assert user is not None
    user_id = user['id']

    # Set description
    r = await client.post(
        '/rpc/settings.Service/UpdateDescription',
        headers={'Content-Type': 'application/proto'},
        content=UpdateDescriptionRequest(description='Hello world').SerializeToString(),
    )
    assert r.is_success, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    assert profile['description'] == 'Hello world'
    assert profile['description_rich_hash'] is not None
    assert profile['description_rich'] == '<p>Hello world</p>\n'  # type: ignore

    # Clear description
    r = await client.post(
        '/rpc/settings.Service/UpdateDescription',
        headers={'Content-Type': 'application/proto'},
        content=UpdateDescriptionRequest(description='').SerializeToString(),
    )
    assert r.is_success, r.text

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
        '/rpc/settings.Service/UpdateSocials',
        headers={'Content-Type': 'application/proto'},
        content=UpdateSocialsRequest(
            socials=[
                UserSocial(service='github', value='octocat'),
                UserSocial(service='signal', value='http://example.com/group'),
            ]
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    socials = [(s.service, s.value) for s in profile['socials']]
    assert socials == [
        ('github', 'octocat'),
        ('signal', 'https://example.com/group'),
    ]

    # Clear again
    r = await client.post(
        '/rpc/settings.Service/UpdateSocials',
        headers={'Content-Type': 'application/proto'},
        content=UpdateSocialsRequest().SerializeToString(),
    )
    assert r.is_success, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    assert profile['socials'] == []


async def test_update_socials_ignores_unsupported_services(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None
    user_id = user['id']

    r = await client.post(
        '/rpc/settings.Service/UpdateSocials',
        headers={'Content-Type': 'application/proto'},
        content=UpdateSocialsRequest(
            socials=[
                UserSocial(service='github', value='octocat'),
                UserSocial(service='unsupported-service', value='ignored'),
            ]
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    profile = await UserProfileQuery.get_by_user_id(user_id)
    socials = [(s.service, s.value) for s in profile['socials']]
    assert socials == [('github', 'octocat')]
