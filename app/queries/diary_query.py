import base64
import re
from asyncio import TaskGroup
from collections import defaultdict
from typing import Any

import cython
from httpx import HTTPError
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.db import db
from app.models.db.diary import Diary
from app.models.db.diary_comment import DiaryComment
from app.models.types import DiaryId, ImageProxyId, LocaleCode, UserId
from app.queries.image_proxy_query import ImageProxyQuery
from app.queries.nominatim_query import NominatimQuery


class DiaryQuery:
    @staticmethod
    async def find_by_id(diary_id: DiaryId) -> Diary | None:
        """Find a diary by id."""
        diaries = await DiaryQuery.find_by_ids([diary_id])
        return next(iter(diaries), None)

    @staticmethod
    async def find_by_ids(ids: list[DiaryId]) -> list[Diary]:
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM diary
                WHERE id = ANY(%s)
                """,
                (ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_by_user(user_id: UserId) -> int:
        """Count diaries by user id."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM diary
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find_recent(
        *,
        user_id: UserId | None = None,
        language: LocaleCode | None = None,
        after: DiaryId | None = None,
        before: DiaryId | None = None,
        limit: int,
    ) -> list[Diary]:
        """Find recent diaries."""
        assert user_id is None or language is None, (
            'Only one of user_id and language can be set'
        )

        order_desc: cython.bint = (after is None) or (before is not None)
        conditions: list[Composable] = []
        params: list[Any] = []

        if user_id is not None:
            conditions.append(SQL('user_id = %s'))
            params.append(user_id)

        if language is not None:
            conditions.append(SQL('language = %s'))
            params.append(language)

        if before is not None:
            conditions.append(SQL('id < %s'))
            params.append(before)

        if after is not None:
            conditions.append(SQL('id > %s'))
            params.append(after)

        query = SQL("""
            SELECT * FROM diary
            WHERE {where}
            ORDER BY id {order}
            LIMIT %s
        """).format(
            where=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
            order=SQL('DESC' if order_desc else 'ASC'),
        )
        params.append(limit)

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = SQL("""
                SELECT * FROM ({})
                ORDER BY id DESC
            """).format(query)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_location_name(diaries: list[Diary]) -> None:
        """Resolve location name fields for diaries."""

        async def task(diary: Diary) -> None:
            try:
                result = await NominatimQuery.reverse(diary['point'])  # pyright: ignore [reportArgumentType]
            except HTTPError:
                pass
            else:
                if result is not None:
                    diary['location_name'] = result.display_name

        async with TaskGroup() as tg:
            for d in diaries:
                if d['point'] is not None:
                    tg.create_task(task(d))

    @staticmethod
    async def resolve_diary(comments: list[DiaryComment]) -> None:
        """Resolve diary fields for the given comments."""
        if not comments:
            return

        id_map = defaultdict[DiaryId, list[DiaryComment]](list)
        for comment in comments:
            id_map[comment['diary_id']].append(comment)

        diaries = await DiaryQuery.find_by_ids(list(id_map))
        for diary in diaries:
            for comment in id_map[diary['id']]:
                comment['diary'] = diary

    @staticmethod
    async def inline_image_thumbnails(objs: list[Diary | DiaryComment]) -> None:
        """
        Inline image thumbnails into body_rich HTML for progressive loading.

        Loads thumbnails from image_proxy table and injects them into the HTML
        using regex replacement. Thumbnails are base64-encoded for inline display.
        """
        if not objs:
            return

        # Collect all proxy IDs from all objects
        all_proxy_ids: set[ImageProxyId] = set()
        for obj in objs:
            proxy_ids = obj.get('image_proxy_ids')
            if proxy_ids:
                all_proxy_ids.update(ImageProxyId(pid) for pid in proxy_ids)

        if not all_proxy_ids:
            return

        # Load all image proxies
        proxies = await ImageProxyQuery.find_by_ids(list(all_proxy_ids))
        proxy_map = {p['id']: p for p in proxies}

        # Pattern to find images with data-proxy-id attribute
        img_pattern = re.compile(
            r'<img\s+([^>]*?)data-proxy-id="(\d+)"([^>]*?)>',
            re.IGNORECASE
        )

        def inline_thumbnail(obj: Diary | DiaryComment) -> None:
            """Inline thumbnails for a single object."""
            body_rich = obj.get('body_rich')
            if not body_rich:
                return

            def replace_with_thumbnail(match: re.Match) -> str:
                before_attrs = match.group(1)
                proxy_id_str = match.group(2)
                after_attrs = match.group(3)

                proxy_id = ImageProxyId(int(proxy_id_str))
                proxy = proxy_map.get(proxy_id)

                # If we have a thumbnail, create progressive loading markup
                if proxy and proxy['thumbnail']:
                    thumbnail_b64 = base64.b64encode(proxy['thumbnail']).decode('ascii')
                    # Use a wrapper div for progressive loading
                    return (
                        f'<span class="progressive-img" data-proxy-id="{proxy_id}">'
                        f'<img {before_attrs}class="thumbnail" '
                        f'src="data:image/webp;base64,{thumbnail_b64}"{after_attrs}>'
                        f'</span>'
                    )

                # No thumbnail available, return original tag
                return match.group(0)

            # Replace all images with progressive loading versions
            obj['body_rich'] = img_pattern.sub(replace_with_thumbnail, body_rich)

        # Process all objects
        for obj in objs:
            inline_thumbnail(obj)
