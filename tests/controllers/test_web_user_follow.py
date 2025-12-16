from httpx import AsyncClient
from starlette import status

from app.lib.auth_context import auth_context
from app.models.types import DisplayName
from app.queries.user_follow_query import UserFollowQuery
from app.queries.user_query import UserQuery


async def test_follow_unfollow_flow(client: AsyncClient):
    """Test complete follow/unfollow workflow."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    assert user1 is not None and user2 is not None

    # Authenticate as user1
    client.headers['Authorization'] = 'User user1'

    # Follow user2
    r = await client.post(f'/api/web/follows/{user2["id"]}/follow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify follow relationship exists
    with auth_context(user1):
        follow_status = await UserFollowQuery.get_follow_status(user2['id'])
        assert follow_status.is_following

    # Verify user1's following page contains user2
    r = await client.post('/api/web/follows/following')
    assert r.status_code == status.HTTP_200_OK
    assert f'/user/{user2["display_name"]}' in r.text
    assert user2['display_name'] in r.text
    assert '<time datetime="' in r.text

    # Verify user2's followers list contains user1
    client.headers['Authorization'] = 'User user2'
    r = await client.post('/api/web/follows/followers')
    assert r.status_code == status.HTTP_200_OK
    assert f'/user/{user1["display_name"]}' in r.text
    assert user1['display_name'] in r.text

    # Unfollow user2
    client.headers['Authorization'] = 'User user1'
    r = await client.post(f'/api/web/follows/{user2["id"]}/unfollow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify follow relationship no longer exists
    with auth_context(user1):
        follow_status = await UserFollowQuery.get_follow_status(user2['id'])
        assert not follow_status.is_following

    # Verify user2 is no longer in user1's following page
    r = await client.post('/api/web/follows/following')
    assert r.status_code == status.HTTP_200_OK
    assert f'/user/{user2["display_name"]}' not in r.text

    # Verify user1 is no longer in user2's followers list
    client.headers['Authorization'] = 'User user2'
    r = await client.post('/api/web/follows/followers')
    assert r.status_code == status.HTTP_200_OK
    assert f'/user/{user1["display_name"]}' not in r.text
