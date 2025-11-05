import logging
import re
from asyncio import TaskGroup
from collections.abc import Iterable
from contextlib import asynccontextmanager
from datetime import timedelta

import cython
from fastapi import HTTPException
from httpx import HTTPStatusError
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL
from zid import zids

from app.config import (
    IMAGE_PROXY_CACHE_EXPIRE,
    IMAGE_PROXY_ERROR_CACHE_EXPIRE,
    IMAGE_PROXY_IMAGE_MAX_SIDE,
    IMAGE_PROXY_RECOMPRESS_QUALITY,
)
from app.db import db
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.image import Image
from app.models.db.image_proxy import ImageProxy
from app.models.proto.server_pb2 import ImageProxyCache
from app.models.types import ImageProxyId, StorageKey
from app.services.cache_service import CacheContext, CacheService
from app.utils import HTTP

_CACHE_CONTEXT = CacheContext('ImageProxy')
_INLINE_RE = re.compile(r'src="/api/web/img/proxy/(\d{1,20})"')
_PREFETCH_TG: TaskGroup


class ImageProxyService:
    @asynccontextmanager
    @staticmethod
    async def context():
        global _PREFETCH_TG
        async with (_PREFETCH_TG := TaskGroup()):  # pyright: ignore[reportConstantRedefinition]
            yield
            for t in _PREFETCH_TG._tasks:  # noqa: SLF001
                t.cancel()

    @staticmethod
    async def ensure(urls: list[str]) -> list[ImageProxy]:
        if not urls:
            return []

        # Deduplicate URLs while preserving order
        unique_urls: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        params = []
        for proxy_id, url in zip(zids(len(unique_urls)), unique_urls, strict=True):
            params.extend((proxy_id, url))

        query = SQL("""
            WITH inserted AS (
                INSERT INTO image_proxy (id, url)
                VALUES {}
                ON CONFLICT (url) DO NOTHING
                RETURNING *
            ),
            existing AS (
                SELECT * FROM image_proxy
                WHERE url = ANY(%s)
                AND NOT EXISTS (
                    SELECT 1 FROM inserted
                    WHERE inserted.url = image_proxy.url
                )
            )
            SELECT * FROM inserted
            UNION ALL
            SELECT * FROM existing
        """).format(SQL(',').join([SQL('(%s, %s)')] * len(unique_urls)))
        params.append(unique_urls)

        async with (
            db(True) as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            rows: dict[str, ImageProxy] = {  # type: ignore
                row['url']: row for row in await r.fetchall()
            }
            result = [rows[url] for url in urls]

        # Prefetch
        async def prefetch(proxy_id: ImageProxyId) -> None:
            try:
                await ImageProxyService.fetch(proxy_id)
            except Exception:
                pass

        prefetch_count: cython.uint = 0

        for row in result:
            if row['thumbnail'] is None:
                _PREFETCH_TG.create_task(prefetch(row['id']))
                prefetch_count += 1

        if prefetch_count:
            logging.debug('Prefetching %d image proxies', prefetch_count)

        return result

    @staticmethod
    async def fetch(proxy_id: ImageProxyId) -> tuple[bytes, str | None]:
        async def factory() -> tuple[bytes, timedelta]:
            return await _generate(proxy_id)

        raw = await CacheService.get(
            StorageKey(str(proxy_id)),
            _CACHE_CONTEXT,
            factory,
        )

        cache = ImageProxyCache.FromString(raw)
        which: str = cache.WhichOneof('result')

        if which == 'normalized':
            return cache.normalized, 'image/webp'
        elif which == 'error':
            raise HTTPException(cache.error.status_code, cache.error.message)
        elif which == 'raw':
            return cache.raw.data, cache.raw.content_type or None
        else:
            raise NotImplementedError('Unsupported image proxy cache type')

    @staticmethod
    async def inline_thumbnails(
        items: Iterable[dict],
        html_field: str,
    ) -> None:
        workload: list[tuple[dict, str]] = []
        ids: set[ImageProxyId] = set()

        for item in items:
            html = item[html_field]
            if not html:
                continue

            has_matches: cython.bint = False

            for match in _INLINE_RE.finditer(html):
                has_matches = True
                ids.add(int(match[1]))  # type: ignore

            if has_matches:
                workload.append((item, html))

        if not workload:
            return

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM image_proxy
                WHERE id = ANY(%s)
                """,
                (list(ids),),
            ) as r,
        ):
            entries: dict[ImageProxyId, ImageProxy] = {
                row['id']: row for row in await r.fetchall()
            }  # type: ignore

        for item, html in workload:

            def repl(match: re.Match[str]) -> str:
                entry = entries.get(int(match[1]))  # type: ignore
                if not entry or not entry['thumbnail']:
                    return match[0]
                padding = 48
                width = entry['width'] + padding
                height = entry['height'] + padding
                return f'{match[0]} width={width} height={height} data-thumbnail={entry["thumbnail"]}'

            item[html_field] = _INLINE_RE.sub(repl, html)

    @staticmethod
    async def prune_unused(ids: list[ImageProxyId]) -> None:
        if not ids:
            return

        async with db(True) as conn:
            result = await conn.execute(
                """
                DELETE FROM image_proxy
                WHERE id = ANY(%s)
                  AND NOT EXISTS (
                    SELECT 1
                    FROM diary
                    WHERE body_image_proxy_ids @> ARRAY[image_proxy.id]
                )
                """,
                (ids,),
            )
            if result.rowcount:
                logging.debug('Pruned %d unused image proxies', result.rowcount)


async def _generate(proxy_id: ImageProxyId) -> tuple[bytes, timedelta]:
    async with db(True) as conn:
        async with await conn.cursor(row_factory=dict_row).execute(
            """
            SELECT * FROM image_proxy
            WHERE id = %s
            FOR UPDATE
            """,
            (proxy_id,),
        ) as r:
            row: ImageProxy | None = await r.fetchone()  # type: ignore
            if row is None:
                raise_for.image_not_found()

        url = row['url']

        # Fetch image from URL
        try:
            response = await HTTP.get(url)
            response.raise_for_status()
        except HTTPStatusError as e:
            logging.debug('Image proxy fetch failed for %s', url, exc_info=True)
            await _clear_thumbnail(conn, proxy_id)
            return (
                ImageProxyCache(
                    error=ImageProxyCache.HttpError(
                        status_code=e.response.status_code,
                        message=str(e),
                    )
                ).SerializeToString(),
                IMAGE_PROXY_ERROR_CACHE_EXPIRE,
            )

        # Try to normalize image
        try:
            processed, img = await Image.normalize_proxy_image(
                response.content,
                quality=IMAGE_PROXY_RECOMPRESS_QUALITY,
                max_side=IMAGE_PROXY_IMAGE_MAX_SIDE,
            )
            width = int(img.shape[1])
            height = int(img.shape[0])
            logging.debug('Processed image proxy %d (%dx%d)', proxy_id, width, height)
        except Exception:
            logging.debug('Image proxy normalization failed for %s', url, exc_info=True)
            await _clear_thumbnail(conn, proxy_id)
            return (
                ImageProxyCache(
                    raw=ImageProxyCache.RawImage(
                        data=response.content,
                        content_type=response.headers.get('content-type'),
                    )
                ).SerializeToString(),
                IMAGE_PROXY_CACHE_EXPIRE,
            )

        # Try to generate thumbnail
        if (
            row['thumbnail'] is None
            or row['thumbnail_updated_at'] is None
            or row['thumbnail_updated_at'] < (utcnow() - IMAGE_PROXY_CACHE_EXPIRE)
        ):
            try:
                thumbnail = await Image.create_proxy_thumbnail(img)
            except Exception:
                logging.info('Image proxy thumbnail failed for %s', url, exc_info=True)
                await _clear_thumbnail(conn, proxy_id)
            else:
                await conn.execute(
                    """
                    UPDATE image_proxy
                    SET width = %s,
                        height = %s,
                        thumbnail = %s,
                        thumbnail_updated_at = statement_timestamp()
                    WHERE id = %s
                    """,
                    (width, height, thumbnail, proxy_id),
                )
                logging.debug('Updated thumbnail for image proxy %d', proxy_id)

        return (
            ImageProxyCache(normalized=processed).SerializeToString(),
            IMAGE_PROXY_CACHE_EXPIRE,
        )


async def _clear_thumbnail(conn: AsyncConnection, proxy_id: ImageProxyId) -> None:
    await conn.execute(
        """
        UPDATE image_proxy
        SET thumbnail = NULL,
            thumbnail_updated_at = statement_timestamp() - %s
        WHERE id = %s
        """,
        (IMAGE_PROXY_CACHE_EXPIRE - IMAGE_PROXY_ERROR_CACHE_EXPIRE, proxy_id),
    )
