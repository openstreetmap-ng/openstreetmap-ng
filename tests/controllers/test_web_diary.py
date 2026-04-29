from base64 import urlsafe_b64decode

from httpx import AsyncClient
from psycopg.rows import dict_row
from re2 import search

from app.db import db
from app.models.proto.diary_pb2 import (
    CreateOrUpdateRequest,
    CreateOrUpdateResponse,
    DeleteRequest,
    DetailsPage,
)
from app.models.types import DiaryId
from app.queries.diary_query import DiaryQuery


def _diary_state(html: str):
    match = search(r'data-state="([^"]+)"', html)
    assert match is not None
    return DetailsPage.FromString(urlsafe_b64decode(match.group(1) + '=='))


async def _create_diary(
    client: AsyncClient,
    *,
    auth: str,
    title: str,
    language: str,
):
    client.headers['Authorization'] = f'User {auth}'
    r = await client.post(
        '/rpc/diary.Service/CreateOrUpdate',
        headers={'Content-Type': 'application/proto'},
        content=CreateOrUpdateRequest(
            title=title,
            body=f'{title} body',
            language=language,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    return int(CreateOrUpdateResponse.FromString(r.content).id)


async def test_diary_lifecycle_with_image_proxy(client: AsyncClient):
    """Test complete diary lifecycle: create with image, update image, delete, verify proxy cleanup."""
    client.headers['Authorization'] = 'User user1'

    image_url = 'https://monicz.dev/favicon.webp'

    # Stage 1: Create diary with external image
    body_1 = f'Test diary entry\n\n![Test image]({image_url})\n\nSome text after.'
    r = await client.post(
        '/rpc/diary.Service/CreateOrUpdate',
        headers={'Content-Type': 'application/proto'},
        content=CreateOrUpdateRequest(
            title='Test Diary',
            body=body_1,
            language='en',
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    diary_id = DiaryId(int(CreateOrUpdateResponse.FromString(r.content).id))

    # Stage 2: Fetch diary page like a browser would
    r = await client.get(f'/diary/{diary_id}')
    assert r.is_success, r.text
    state = _diary_state(r.text)

    # Verify title and image proxy in page state
    assert state.entry.title == 'Test Diary'
    assert 'alt="Test image"' in state.entry.body_rich
    assert '/api/web/img/proxy/' in state.entry.body_rich
    assert image_url not in state.entry.body_rich

    # Verify proxy exists in database with correct URL
    async with (
        db() as conn,
        await conn.cursor(row_factory=dict_row).execute(
            """
            SELECT * FROM image_proxy
            WHERE url = %s
            """,
            (image_url,),
        ) as r,
    ):
        proxy = await r.fetchone()
    assert proxy is not None

    # Stage 3: Fetch proxied image
    r = await client.get(f'/api/web/img/proxy/{proxy["id"]}')
    assert r.is_success
    assert r.headers['content-type'].startswith('image/')
    assert r.content

    # Stage 4: Update diary with same image
    body_2 = f'Updated entry\n\n![New image]({image_url})'
    r = await client.post(
        '/rpc/diary.Service/CreateOrUpdate',
        headers={'Content-Type': 'application/proto'},
        content=CreateOrUpdateRequest(
            diary_id=diary_id,
            title='Updated Title',
            body=body_2,
            language='en',
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    # Stage 5: Fetch updated diary page
    r = await client.get(f'/diary/{diary_id}')
    assert r.is_success, r.text
    state = _diary_state(r.text)

    # Verify updated content and same proxy still used
    assert state.entry.title == 'Updated Title'
    assert 'alt="New image"' in state.entry.body_rich
    assert f'/api/web/img/proxy/{proxy["id"]}' in state.entry.body_rich
    assert image_url not in state.entry.body_rich

    # Stage 6: Delete diary
    r = await client.post(
        '/rpc/diary.Service/Delete',
        headers={'Content-Type': 'application/proto'},
        content=DeleteRequest(diary_id=diary_id).SerializeToString(),
    )
    assert r.is_success, r.text

    # Verify diary deleted
    diary = await DiaryQuery.find_by_id(diary_id)
    assert diary is None

    # Stage 7: Verify our diary no longer references the proxy
    async with (
        db() as conn,
        await conn.execute(
            """
            SELECT 1 FROM diary
            WHERE id = %s
              AND body_image_proxy_ids @> ARRAY[%s]
            """,
            (diary_id, proxy['id']),
        ) as r,
    ):
        result = await r.fetchone()
        assert result is None


async def test_diary_user_index_not_found(client: AsyncClient):
    r = await client.get('/user/definitely-missing/diary')
    assert r.status_code == 404, r.text


async def test_diary_rss_feeds(client: AsyncClient):
    title_all = 'test_diary_rss_feeds_all_en'
    title_user = 'test_diary_rss_feeds_user2_pl'
    await _create_diary(client, auth='user1', title=title_all, language='en')
    await _create_diary(client, auth='user2', title=title_user, language='pl')

    r = await client.get('/diary/rss')
    assert r.is_success, r.text
    assert r.headers['content-type'].startswith('application/rss+xml')
    assert title_all in r.text
    assert title_user in r.text

    r = await client.get('/diary/en/rss')
    assert r.is_success, r.text
    assert title_all in r.text
    assert title_user not in r.text

    client.headers['Authorization'] = 'User user2'
    r = await client.get('/user/user2/diary/rss')
    assert r.is_success, r.text
    assert title_user in r.text
    assert title_all not in r.text


async def test_diary_invalid_language_returns_not_found(client: AsyncClient):
    r = await client.get('/diary/not-a-real-locale')
    assert r.status_code == 404, r.text


async def test_diary_edit_other_user_returns_not_found(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/rpc/diary.Service/CreateOrUpdate',
        headers={'Content-Type': 'application/proto'},
        content=CreateOrUpdateRequest(
            title='test_diary_edit_other_user_returns_not_found',
            body='Hello from a test diary entry.',
            language='en',
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    diary_id = int(CreateOrUpdateResponse.FromString(r.content).id)

    client.headers['Authorization'] = 'User user2'

    r = await client.get(f'/diary/{diary_id}/edit')
    assert r.status_code == 404, r.text
