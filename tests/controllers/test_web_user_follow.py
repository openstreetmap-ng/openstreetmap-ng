from httpx import AsyncClient

from app.lib.auth.context import auth_context
from app.models.proto.follow_pb2 import (
    ListRequest,
    ListResponse,
    UpdateRequest,
)
from app.models.proto.follow_types import Tab
from app.models.types import DisplayName
from app.queries.user_follow_query import UserFollowQuery
from app.queries.user_query import UserQuery


async def _list(client: AsyncClient, *, tab: Tab) -> ListResponse:
    r = await client.post(
        '/rpc/follow.Service/List',
        content=ListRequest(tab=tab).SerializeToString(),
        headers={'Content-Type': 'application/proto'},
    )
    assert r.is_success, r.text
    return ListResponse.FromString(r.content)


async def _update(client: AsyncClient, *, target_user_id: int, is_following: bool):
    r = await client.post(
        '/rpc/follow.Service/Update',
        content=UpdateRequest(
            target_user_id=target_user_id, is_following=is_following
        ).SerializeToString(),
        headers={'Content-Type': 'application/proto'},
    )
    assert r.is_success, r.text


async def test_follow_unfollow_flow(client: AsyncClient):
    """Test complete follow/unfollow workflow."""
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    assert user1 is not None and user2 is not None

    # Authenticate as user1
    client.headers['Authorization'] = 'User user1'

    # Follow user2
    await _update(client, target_user_id=user2['id'], is_following=True)

    # Verify follow relationship exists
    with auth_context(user1):
        follow_status = await UserFollowQuery.get_follow_status(user2['id'])
        assert follow_status.is_following

    # Verify user1's following page contains user2
    resp = await _list(client, tab='following')
    assert any(e.user.display_name == user2['display_name'] for e in resp.entries)

    # Verify user2's followers list contains user1
    client.headers['Authorization'] = 'User user2'
    resp = await _list(client, tab='followers')
    assert any(e.user.display_name == user1['display_name'] for e in resp.entries)

    # Unfollow user2
    client.headers['Authorization'] = 'User user1'
    await _update(client, target_user_id=user2['id'], is_following=False)

    # Verify follow relationship no longer exists
    with auth_context(user1):
        follow_status = await UserFollowQuery.get_follow_status(user2['id'])
        assert not follow_status.is_following

    # Verify user2 is no longer in user1's following page
    resp = await _list(client, tab='following')
    assert all(e.user.display_name != user2['display_name'] for e in resp.entries)

    # Verify user1 is no longer in user2's followers list
    client.headers['Authorization'] = 'User user2'
    resp = await _list(client, tab='followers')
    assert all(e.user.display_name != user1['display_name'] for e in resp.entries)
