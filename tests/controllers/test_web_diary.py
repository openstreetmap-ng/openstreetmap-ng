from httpx import AsyncClient
from psycopg.rows import dict_row

from app.db import db
from app.models.types import DiaryId
from app.queries.diary_query import DiaryQuery


async def test_diary_lifecycle_with_image_proxy(client: AsyncClient):
    """Test complete diary lifecycle: create with image, update image, delete, verify proxy cleanup."""
    client.headers['Authorization'] = 'User user1'

    image_url = 'https://monicz.dev/favicon.webp'

    # Stage 1: Create diary with external image
    body_1 = f'Test diary entry\n\n![Test image]({image_url})\n\nSome text after.'
    r = await client.post(
        '/api/web/diary',
        data={
            'title': 'Test Diary',
            'body': body_1,
            'language': 'en',
        },
    )
    assert r.is_success, r.text
    diary_id = DiaryId(int(r.json()['redirect_url'].split('/')[-1]))

    # Stage 2: Fetch diary page like a browser would
    r = await client.get(f'/diary/{diary_id}')
    assert r.is_success, r.text
    html = r.text

    # Verify title and image proxy in rendered HTML
    assert 'Test Diary' in html
    assert 'alt="Test image"' in html
    assert '/api/web/img/proxy/' in html
    assert image_url not in html

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
        '/api/web/diary',
        data={
            'title': 'Updated Title',
            'body': body_2,
            'language': 'en',
            'diary_id': diary_id,
        },
    )
    assert r.is_success, r.text

    # Stage 5: Fetch updated diary page
    r = await client.get(f'/diary/{diary_id}')
    assert r.is_success, r.text
    html = r.text

    # Verify updated content and same proxy still used
    assert 'Updated Title' in html
    assert 'alt="New image"' in html
    assert f'/api/web/img/proxy/{proxy["id"]}' in html
    assert image_url not in html

    # Stage 6: Delete diary
    r = await client.post(f'/api/web/diary/{diary_id}/delete')
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
