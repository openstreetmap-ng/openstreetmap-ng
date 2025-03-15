from psycopg.abc import Params, Query
from psycopg.rows import dict_row

from app.db import db2
from app.lib.standard_pagination import standard_pagination_range
from app.limits import CHANGESET_COMMENTS_PAGE_SIZE
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment, changeset_comments_resolve_rich_text
from app.models.types import ChangesetId


class ChangesetCommentQuery:
    @staticmethod
    async def get_comments_page(
        changeset_id: ChangesetId,
        *,
        page: int,
        num_items: int,
    ) -> list[ChangesetComment]:
        """Get comments for the given changeset comments page."""
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=CHANGESET_COMMENTS_PAGE_SIZE,
            num_items=num_items,
        )

        async with (
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM (
                    SELECT * FROM changeset_comment
                    WHERE changeset_id = %s
                    ORDER BY id DESC
                    OFFSET %s
                    LIMIT %s
                )
                ORDER BY id ASC
                """,
                (changeset_id, stmt_offset, stmt_limit),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_num_comments(changesets: list[Changeset]) -> None:
        """Resolve the number of comments for each changeset."""
        if not changesets:
            return

        id_map = {changeset['id']: changeset for changeset in changesets}

        async with (
            db2() as conn,
            await conn.execute(
                """
                SELECT c.value, (
                    SELECT COUNT(*) FROM changeset_comment
                    WHERE changeset_id = c.value
                ) FROM unnest(%s) AS c(value)
                """,
                (list(id_map),),
            ) as r,
        ):
            for changeset_id, count in await r.fetchall():
                id_map[changeset_id]['num_comments'] = count

    @staticmethod
    async def resolve_comments(
        changesets: list[Changeset],
        *,
        limit_per_changeset: int | None,
        resolve_rich_text: bool = False,
    ) -> list[ChangesetComment]:
        """Resolve comments for changesets. Returns the resolved comments."""
        if not changesets:
            return []

        id_map: dict[ChangesetId, list[ChangesetComment]] = {}
        for changeset in changesets:
            id_map[changeset['id']] = changeset['comments'] = []

        query: Query
        params: Params
        if limit_per_changeset is not None:
            # Using window functions to limit comments per changeset
            query = """
            WITH ranked_comments AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY changeset_id ORDER BY id DESC) AS _row_number
                FROM changeset_comment
                WHERE changeset_id = ANY(%s)
            )
            SELECT * FROM ranked_comments
            WHERE _row_number <= %s
            ORDER BY changeset_id, id
            """
            params = (list(id_map), limit_per_changeset)
        else:
            # Without limit, just fetch all comments
            query = """
            SELECT * FROM changeset_comment
            WHERE changeset_id = ANY(%s)
            ORDER BY changeset_id, id
            """
            params = (list(id_map),)

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            comments: list[ChangesetComment] = await r.fetchall()  # type: ignore

        current_changeset_id: ChangesetId | None = None
        current_comments: list[ChangesetComment] = []

        for comment in comments:
            changeset_id = comment['changeset_id']
            if current_changeset_id != changeset_id:
                current_changeset_id = changeset_id
                current_comments = id_map[changeset_id]
            current_comments.append(comment)

        for changeset in changesets:
            changeset['num_comments'] = len(changeset['comments'])  # pyright: ignore [reportTypedDictNotRequiredAccess]

        if resolve_rich_text:
            await changeset_comments_resolve_rich_text(comments)

        return comments
