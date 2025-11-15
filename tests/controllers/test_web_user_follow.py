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

    # Verify user1's following list contains user2
    with auth_context(user1):
        following = await UserFollowQuery.list_user_follows(
            user1['id'], followers=False, page=1, num_items=100
        )
        user2_follow = next((f for f in following if f['id'] == user2['id']), None)
        assert user2_follow is not None
        assert user2_follow['display_name'] == user2['display_name']
        assert 'created_at' in user2_follow

    # Verify user2's followers list contains user1
    with auth_context(user2):
        followers = await UserFollowQuery.list_user_follows(
            user2['id'], followers=True, page=1, num_items=100
        )
        user1_follower = next((f for f in followers if f['id'] == user1['id']), None)
        assert user1_follower is not None
        assert user1_follower['display_name'] == user1['display_name']

    # Unfollow user2
    r = await client.post(f'/api/web/follows/{user2["id"]}/unfollow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify follow relationship no longer exists
    with auth_context(user1):
        follow_status = await UserFollowQuery.get_follow_status(user2['id'])
        assert not follow_status.is_following

    # Verify user2 is no longer in user1's following list
    with auth_context(user1):
        following = await UserFollowQuery.list_user_follows(
            user1['id'], followers=False, page=1, num_items=100
        )
        assert not any(f['id'] == user2['id'] for f in following)

    # Verify user1 is no longer in user2's followers list
    with auth_context(user2):
        followers = await UserFollowQuery.list_user_follows(
            user2['id'], followers=True, page=1, num_items=100
        )
        assert not any(f['id'] == user1['id'] for f in followers)
