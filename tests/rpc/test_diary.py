from httpx import AsyncClient

from app.models.proto.diary_pb2 import (
    AddCommentRequest,
    CreateOrUpdateRequest,
    CreateOrUpdateResponse,
    GetCommentsRequest,
    GetCommentsResponse,
    GetPageRequest,
    GetPageResponse,
    GetUserCommentsPageRequest,
    GetUserCommentsPageResponse,
)
from app.models.types import DisplayName
from app.queries.user_query import UserQuery


async def _create_diary_with_comment(client: AsyncClient, *, title: str, comment: str):
    r = await client.post(
        '/rpc/diary.Service/CreateOrUpdate',
        headers={'Content-Type': 'application/proto'},
        content=CreateOrUpdateRequest(
            title=title,
            body='Hello from a test diary entry.',
            language='en',
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    diary_id = int(CreateOrUpdateResponse.FromString(r.content).id)

    r = await client.post(
        '/rpc/diary.Service/AddComment',
        headers={'Content-Type': 'application/proto'},
        content=AddCommentRequest(diary_id=diary_id, body=comment).SerializeToString(),
    )
    assert r.is_success, r.text
    return diary_id


async def test_get_page(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    title = test_get_page.__qualname__
    r = await client.post(
        '/rpc/diary.Service/CreateOrUpdate',
        headers={'Content-Type': 'application/proto'},
        content=CreateOrUpdateRequest(
            title=title,
            body='Hello from a test diary entry.',
            language='en',
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    client.headers.pop('Authorization')

    r = await client.post(
        '/rpc/diary.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest().SerializeToString(),
    )
    assert r.is_success, r.text

    response = GetPageResponse.FromString(r.content)
    assert response.diaries[0].title == title


async def test_get_comment_pages(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    diary_title = test_get_comment_pages.__qualname__
    comment = 'User diary comments page'
    diary_id = await _create_diary_with_comment(
        client,
        title=diary_title,
        comment=comment,
    )

    client.headers.pop('Authorization')

    r = await client.post(
        '/rpc/diary.Service/GetComments',
        headers={'Content-Type': 'application/proto'},
        content=GetCommentsRequest(diary_id=diary_id).SerializeToString(),
    )
    assert r.is_success, r.text

    comments_response = GetCommentsResponse.FromString(r.content)
    assert (
        comments_response.comments[0].body_rich == '<p>User diary comments page</p>\n'
    )

    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None

    r = await client.post(
        '/rpc/diary.Service/GetUserCommentsPage',
        headers={'Content-Type': 'application/proto'},
        content=GetUserCommentsPageRequest(user_id=user['id']).SerializeToString(),
    )
    assert r.is_success, r.text

    response = GetUserCommentsPageResponse.FromString(r.content)
    assert response.entries[0].diary_title == diary_title
    assert response.entries[0].body_rich == '<p>User diary comments page</p>\n'
