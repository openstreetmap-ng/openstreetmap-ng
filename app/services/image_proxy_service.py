import logging
from datetime import datetime, timezone

from httpx import HTTPError, HTTPStatusError

from app.config import (
    IMAGE_PROXY_CACHE_EXPIRE,
    IMAGE_PROXY_ERROR_CACHE_EXPIRE,
    IMAGE_PROXY_FETCH_TIMEOUT,
    IMAGE_PROXY_THUMBNAIL_REFRESH,
)
from app.lib.crypto import hash_storage_key
from app.lib.exceptions_context import raise_for
from app.lib.image import Image
from app.models.db.image_proxy import ImageProxy
from app.models.types import ImageProxyId, StorageKey
from app.queries.image_proxy_query import ImageProxyQuery
from app.services.cache_service import CacheService, CacheContext
from app.utils import HTTP


class ImageProxyService:
    _CACHE_CONTEXT = CacheContext('ImageProxy')

    @staticmethod
    async def get_or_fetch_image(proxy_id: ImageProxyId) -> bytes:
        """
        Get proxied image from cache or fetch and process from original URL.

        Uses cache for processed images with configured TTL.
        Errors are also cached (shorter TTL).
        """
        proxy = await ImageProxyQuery.find_by_id(proxy_id)
        if proxy is None:
            raise_for.image_proxy_not_found(proxy_id)

        # Check if we have a recent error cached
        if proxy['error_at'] is not None:
            error_age = datetime.now(timezone.utc) - proxy['error_at']
            if error_age < IMAGE_PROXY_ERROR_CACHE_EXPIRE:
                logging.debug('Image proxy %d has recent error (age: %s)', proxy_id, error_age)
                raise_for.image_proxy_fetch_failed(proxy['url'])

        cache_key = hash_storage_key(f'image:{proxy_id}')

        try:
            image_data = await CacheService.get(
                cache_key,
                ImageProxyService._CACHE_CONTEXT,
                lambda: ImageProxyService._fetch_and_process(proxy),
                ttl=IMAGE_PROXY_CACHE_EXPIRE,
            )

            # Background task: ensure thumbnail exists and is fresh
            # Note: This doesn't block the response
            await ImageProxyService._ensure_thumbnail_exists(proxy, image_data)

            return image_data

        except Exception as e:
            logging.warning('Failed to fetch image proxy %d: %s', proxy_id, e)
            # Mark error in database (acts as error cache via error_at field)
            await ImageProxyQuery.mark_error(proxy_id)
            raise_for.image_proxy_fetch_failed(proxy['url'])

    @staticmethod
    async def _fetch_and_process(proxy: ImageProxy) -> bytes:
        """Fetch original image and process (resize, recompress)."""
        logging.debug('Fetching image from %s', proxy['url'])

        try:
            response = await HTTP.get(
                proxy['url'],
                timeout=IMAGE_PROXY_FETCH_TIMEOUT.total_seconds(),
            )
            response.raise_for_status()
        except (HTTPError, HTTPStatusError) as e:
            logging.warning('HTTP error fetching %s: %s', proxy['url'], e)
            raise_for.image_proxy_fetch_failed(proxy['url'])

        if not response.content:
            raise_for.image_proxy_fetch_failed(proxy['url'])

        # Process image (resize, recompress to WebP)
        try:
            return await Image.process_proxy_image(response.content)
        except Exception as e:
            logging.warning('Failed to process image %s: %s', proxy['url'], e)
            raise_for.bad_image_format()

    @staticmethod
    async def _ensure_thumbnail_exists(proxy: ImageProxy, processed_image_data: bytes) -> None:
        """
        Ensure thumbnail exists and is fresh.

        Uses FOR UPDATE SKIP LOCKED within a single transaction to avoid duplicate work.
        """
        needs_refresh = (
            proxy['thumbnail'] is None
            or proxy['thumbnail_updated_at'] is None
            or (datetime.now(timezone.utc) - proxy['thumbnail_updated_at']) > IMAGE_PROXY_THUMBNAIL_REFRESH
        )

        if not needs_refresh:
            return

        try:
            # Lock row and check again in single transaction
            from app.db import db  # noqa: PLC0415
            from psycopg.rows import dict_row  # noqa: PLC0415

            async with db(write=True) as conn:
                # Try to acquire lock - SKIP LOCKED means we skip if another process has it
                async with await conn.cursor(row_factory=dict_row).execute(
                    """
                    SELECT * FROM image_proxy
                    WHERE id = %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (proxy['id'],),
                ) as r:
                    locked_proxy = await r.fetchone()

                if locked_proxy is None:
                    # Another process has the lock, skip
                    return

                # Double-check after lock acquired
                needs_refresh = (
                    locked_proxy['thumbnail'] is None
                    or locked_proxy['thumbnail_updated_at'] is None
                    or (datetime.now(timezone.utc) - locked_proxy['thumbnail_updated_at']) > IMAGE_PROXY_THUMBNAIL_REFRESH
                )

                if not needs_refresh:
                    return

                # Generate thumbnail from processed image
                thumbnail_data = await Image.create_thumbnail(processed_image_data)

                # Update in same transaction
                await conn.execute(
                    """
                    UPDATE image_proxy
                    SET thumbnail = %s,
                        thumbnail_updated_at = statement_timestamp(),
                        error_at = NULL,
                        updated_at = statement_timestamp()
                    WHERE id = %s
                    """,
                    (thumbnail_data, proxy['id']),
                )
                logging.debug('Updated thumbnail for image proxy %d', proxy['id'])

        except Exception as e:
            logging.warning('Failed to create thumbnail for proxy %d: %s', proxy['id'], e)
            # Don't raise - thumbnail generation failure shouldn't block image serving

    @staticmethod
    async def prefetch_image(proxy_id: ImageProxyId) -> None:
        """
        Prefetch and prepare thumbnail for an image proxy.

        Called in background when new images are detected in markdown.
        """
        try:
            await ImageProxyService.get_or_fetch_image(proxy_id)
        except Exception as e:
            logging.debug('Prefetch failed for proxy %d: %s', proxy_id, e)
            # Prefetch failures are not critical

    @staticmethod
    async def cleanup_orphaned_proxies(old_proxy_ids: list[ImageProxyId]) -> None:
        """
        Clean up image proxy entries that are no longer used by any diary/comment.

        Should be called when diary/comment is deleted or updated.
        """
        if not old_proxy_ids:
            return

        orphaned_ids = await ImageProxyQuery.find_orphaned_ids(old_proxy_ids)
        if orphaned_ids:
            logging.debug('Cleaning up %d orphaned image proxies', len(orphaned_ids))
            await ImageProxyQuery.delete_by_ids(orphaned_ids)

            # Also clean cache for deleted proxies
            for proxy_id in orphaned_ids:
                cache_key = hash_storage_key(f'image:{proxy_id}')
                CacheService.delete(ImageProxyService._CACHE_CONTEXT, cache_key)
