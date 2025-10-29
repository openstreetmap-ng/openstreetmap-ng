from psycopg.rows import dict_row
from psycopg.sql import SQL

from app.db import db
from app.models.db.image_proxy import ImageProxy, ImageProxyInit
from app.models.types import ImageProxyId


class ImageProxyQuery:
    @staticmethod
    async def find_by_id(proxy_id: ImageProxyId, *, for_update: bool = False) -> ImageProxy | None:
        """Find an image proxy by id."""
        proxies = await ImageProxyQuery.find_by_ids([proxy_id], for_update=for_update)
        return next(iter(proxies), None)

    @staticmethod
    async def find_by_ids(ids: list[ImageProxyId], *, for_update: bool = False) -> list[ImageProxy]:
        """Find image proxies by ids."""
        query_parts = ['SELECT * FROM image_proxy WHERE id = ANY(%s)']
        if for_update:
            query_parts.append('FOR UPDATE')

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                SQL(' '.join(query_parts)),
                (ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_or_create_by_url(url: str) -> ImageProxyId:
        """
        Find or create an image proxy entry by URL.

        Uses INSERT ... ON CONFLICT to handle race conditions.
        Returns the proxy ID.
        """
        async with (
            db(write=True) as conn,
            await conn.execute(
                """
                INSERT INTO image_proxy (url)
                VALUES (%s)
                ON CONFLICT (url) DO UPDATE
                SET url = EXCLUDED.url
                RETURNING id
                """,
                (url,),
            ) as r,
        ):
            row = await r.fetchone()
            return ImageProxyId(row[0])  # type: ignore

    @staticmethod
    async def find_by_url(url: str, *, for_update_skip_locked: bool = False) -> ImageProxy | None:
        """
        Find an image proxy by URL.

        If for_update_skip_locked is True, uses FOR UPDATE SKIP LOCKED to avoid blocking.
        """
        query_parts = ['SELECT * FROM image_proxy WHERE url = %s']
        if for_update_skip_locked:
            query_parts.append('FOR UPDATE SKIP LOCKED')

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                SQL(' '.join(query_parts)),
                (url,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def update_thumbnail(
        proxy_id: ImageProxyId,
        thumbnail: bytes | None,
    ) -> None:
        """Update thumbnail and thumbnail_updated_at."""
        async with db(write=True) as conn:
            await conn.execute(
                """
                UPDATE image_proxy
                SET thumbnail = %s,
                    thumbnail_updated_at = statement_timestamp(),
                    error_at = NULL,
                    updated_at = statement_timestamp()
                WHERE id = %s
                """,
                (thumbnail, proxy_id),
            )

    @staticmethod
    async def mark_error(proxy_id: ImageProxyId) -> None:
        """Mark proxy as having an error."""
        async with db(write=True) as conn:
            await conn.execute(
                """
                UPDATE image_proxy
                SET error_at = statement_timestamp(),
                    thumbnail = NULL,
                    thumbnail_updated_at = NULL,
                    updated_at = statement_timestamp()
                WHERE id = %s
                """,
                (proxy_id,),
            )

    @staticmethod
    async def delete_by_ids(ids: list[ImageProxyId]) -> None:
        """Delete image proxy entries by IDs."""
        if not ids:
            return

        async with db(write=True) as conn:
            await conn.execute(
                """
                DELETE FROM image_proxy
                WHERE id = ANY(%s)
                """,
                (ids,),
            )

    @staticmethod
    async def find_orphaned_ids(current_ids: list[ImageProxyId]) -> list[ImageProxyId]:
        """
        Find proxy IDs that are no longer used by any diary or diary comment.

        Returns IDs from current_ids that are not referenced anywhere.
        """
        if not current_ids:
            return []

        async with (
            db() as conn,
            await conn.execute(
                """
                WITH used_ids AS (
                    SELECT DISTINCT unnest(image_proxy_ids) AS id
                    FROM diary
                    WHERE image_proxy_ids IS NOT NULL
                    UNION
                    SELECT DISTINCT unnest(image_proxy_ids) AS id
                    FROM diary_comment
                    WHERE image_proxy_ids IS NOT NULL
                )
                SELECT id FROM unnest(%s::bigint[]) AS id
                WHERE id NOT IN (SELECT id FROM used_ids)
                """,
                (current_ids,),
            ) as r,
        ):
            rows = await r.fetchall()
            return [ImageProxyId(row[0]) for row in rows]  # type: ignore
