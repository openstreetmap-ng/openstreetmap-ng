import pytest
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

    # Authenticate as user1
    client.headers['Authorization'] = 'User user1'

    # Follow user2
    r = await client.post(f'/api/web/user-follow/{user2["id"]}/follow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify follow relationship exists
    with auth_context(user1):
        is_following = await UserFollowQuery.is_following(user2['id'])
        assert is_following

    # Verify user1's following list contains user2
    with auth_context(user1):
        following = await UserFollowQuery.list_following(user1['id'])
        assert len(following) == 1
        assert following[0]['id'] == user2['id']
        assert following[0]['display_name'] == user2['display_name']
        assert 'created_at' in following[0]

    # Verify user2's followers list contains user1
    with auth_context(user2):
        followers = await UserFollowQuery.list_followers(user2['id'])
        assert len(followers) == 1
        assert followers[0]['id'] == user1['id']
        assert followers[0]['display_name'] == user1['display_name']

    # Unfollow user2
    r = await client.post(f'/api/web/user-follow/{user2["id"]}/unfollow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify follow relationship no longer exists
    with auth_context(user1):
        is_following = await UserFollowQuery.is_following(user2['id'])
        assert not is_following

    # Verify user1's following list is empty
    with auth_context(user1):
        following = await UserFollowQuery.list_following(user1['id'])
        assert len(following) == 0

    # Verify user2's followers list is empty
    with auth_context(user2):
        followers = await UserFollowQuery.list_followers(user2['id'])
        assert len(followers) == 0


async def test_follow_idempotency(client: AsyncClient):
    """Test that following the same user twice is idempotent."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))

    # Authenticate as user1
    client.headers['Authorization'] = 'User user1'

    # Follow user2 first time
    r = await client.post(f'/api/web/user-follow/{user2["id"]}/follow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Follow user2 second time (should be idempotent)
    r = await client.post(f'/api/web/user-follow/{user2["id"]}/follow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify only one follow relationship exists
    with auth_context(user1):
        following = await UserFollowQuery.list_following(user1['id'])
        assert len(following) == 1

    # Cleanup
    await client.post(f'/api/web/user-follow/{user2["id"]}/unfollow')


async def test_unfollow_idempotency(client: AsyncClient):
    """Test that unfollowing when not following is idempotent."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))

    # Authenticate as user1
    client.headers['Authorization'] = 'User user1'

    # Unfollow user2 when not following (should be idempotent)
    r = await client.post(f'/api/web/user-follow/{user2["id"]}/unfollow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify no follow relationship exists
    with auth_context(user1):
        is_following = await UserFollowQuery.is_following(user2['id'])
        assert not is_following


async def test_follow_back(client: AsyncClient):
    """Test reciprocal follow (follow back) scenario."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))

    # Stage 1: user1 follows user2
    client.headers['Authorization'] = 'User user1'
    r = await client.post(f'/api/web/user-follow/{user2["id"]}/follow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Stage 2: user2 follows user1 back
    client.headers['Authorization'] = 'User user2'
    r = await client.post(f'/api/web/user-follow/{user1["id"]}/follow')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify reciprocal follows exist
    with auth_context(user1):
        is_following_user2 = await UserFollowQuery.is_following(user2['id'])
        assert is_following_user2

    with auth_context(user2):
        is_following_user1 = await UserFollowQuery.is_following(user1['id'])
        assert is_following_user1

    # Cleanup
    client.headers['Authorization'] = 'User user1'
    await client.post(f'/api/web/user-follow/{user2["id"]}/unfollow')
    client.headers['Authorization'] = 'User user2'
    await client.post(f'/api/web/user-follow/{user1["id"]}/unfollow')


async def test_self_follow_prevented(client: AsyncClient):
    """Test that users cannot follow themselves."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))

    # Authenticate as user1
    client.headers['Authorization'] = 'User user1'

    # Try to follow self (should fail)
    r = await client.post(f'/api/web/user-follow/{user1["id"]}/follow')
    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_follow_nonexistent_user(client: AsyncClient):
    """Test that following a nonexistent user fails."""
    # Authenticate as user1
    client.headers['Authorization'] = 'User user1'

    # Try to follow nonexistent user
    nonexistent_user_id = 999999999
    r = await client.post(f'/api/web/user-follow/{nonexistent_user_id}/follow')
    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_follows_page_requires_auth(client: AsyncClient):
    """Test that /follows page requires authentication."""
    # Try to access without authentication
    r = await client.get('/follows')
    assert r.status_code == status.HTTP_401_UNAUTHORIZED


async def test_follows_page_content(client: AsyncClient):
    """Test that /follows page displays correct content."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    user3 = await UserQuery.find_by_display_name(DisplayName('user3'))

    # Setup: user1 follows user2, user3 follows user1
    client.headers['Authorization'] = 'User user1'
    await client.post(f'/api/web/user-follow/{user2["id"]}/follow')

    client.headers['Authorization'] = 'User user3'
    await client.post(f'/api/web/user-follow/{user1["id"]}/follow')

    # Test: user1 views their follows page
    client.headers['Authorization'] = 'User user1'
    r = await client.get('/follows')
    assert r.is_success
    html = r.text

    # Verify following section contains user2
    assert 'user2' in html

    # Verify followers section contains user3
    assert 'user3' in html

    # Cleanup
    await client.post(f'/api/web/user-follow/{user2["id"]}/unfollow')
    client.headers['Authorization'] = 'User user3'
    await client.post(f'/api/web/user-follow/{user1["id"]}/unfollow')


async def test_resolve_is_following(client: AsyncClient):
    """Test resolve_is_following helper function."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    user3 = await UserQuery.find_by_display_name(DisplayName('user3'))

    # Setup: user1 follows user2 (but not user3)
    client.headers['Authorization'] = 'User user1'
    await client.post(f'/api/web/user-follow/{user2["id"]}/follow')

    # Test resolve_is_following
    with auth_context(user1):
        users_list = [
            {'id': user2['id'], 'display_name': user2['display_name']},
            {'id': user3['id'], 'display_name': user3['display_name']},
        ]

        await UserFollowQuery.resolve_is_following(users_list)

        # user2 should have is_following=True
        assert users_list[0].get('is_following') is True
        # user3 should not have is_following key (or False)
        assert users_list[1].get('is_following') is not True

    # Cleanup
    await client.post(f'/api/web/user-follow/{user2["id"]}/unfollow')
