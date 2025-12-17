from httpx import AsyncClient

from app.models.types import DisplayName
from app.queries.user_query import UserQuery


async def test_diary_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    title = test_diary_page_standard_pagination.__qualname__
    r = await client.post(
        '/api/web/diary',
        data={
            'title': title,
            'body': 'Hello from a test diary entry.',
            'language': 'en',
        },
    )
    assert r.is_success, r.text

    client.headers.pop('Authorization')

    r = await client.post(
        '/api/web/diary/page',
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert r.is_success, r.text
    assert 'X-StandardPagination' in r.headers
    assert title in r.text


async def test_diary_user_comments_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    diary_title = test_diary_user_comments_page_standard_pagination.__qualname__
    r = await client.post(
        '/api/web/diary',
        data={
            'title': diary_title,
            'body': 'Hello from a test diary entry.',
            'language': 'en',
        },
    )
    assert r.is_success, r.text
    diary_id = int(r.json()['redirect_url'].split('/')[-1])

    comment_text = 'Pagination user comments test'
    r = await client.post(
        f'/api/web/diary/{diary_id}/comment',
        data={'body': comment_text},
    )
    assert r.is_success, r.text

    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user1 is not None

    client.headers.pop('Authorization')

    r = await client.post(
        f'/api/web/diary/user/{user1["id"]}/comments',
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert r.is_success, r.text
    assert 'X-StandardPagination' in r.headers
    assert diary_title in r.text
    assert comment_text in r.text
