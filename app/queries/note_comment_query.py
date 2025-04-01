from typing import Any, Literal

from psycopg.abc import Params, Query
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from shapely.geometry.base import BaseGeometry

from app.config import NOTE_COMMENTS_PAGE_SIZE
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.db.user import user_is_moderator
from app.models.types import NoteId


class NoteCommentQuery:
    @staticmethod
    async def legacy_find_many_by_query(
        *,
        geometry: BaseGeometry | None = None,
        limit: int | None = None,
    ) -> list[NoteComment]:
        """Find note comments by query."""
        conditions: list[Composable] = []
        params: list[Any] = []

        # Only show hidden notes to moderators
        if not user_is_moderator(auth_user()):
            conditions.append(SQL('note.hidden_at IS NULL'))

        if geometry is not None:
            conditions.append(SQL('ST_Intersects(note.point, %s)'))
            params.append(geometry)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM note_comment
            JOIN note ON note_id = note.id
            WHERE {conditions}
            ORDER BY id DESC
            {limit}
        """).format(
            conditions=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
            limit=limit_clause,
        )

        async with db() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def get_comments_page(
        note_id: NoteId,
        *,
        page: int,
        num_items: int,
        skip_header: bool = True,
    ) -> list[NoteComment]:
        """
        Get comments for the given note comments page.
        The header comment is omitted if it's the first page.
        """
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=NOTE_COMMENTS_PAGE_SIZE,
            num_items=num_items,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM (
                    SELECT * FROM note_comment
                    WHERE note_id = %s
                    ORDER BY id DESC
                    OFFSET %s
                    LIMIT %s
                ) AS subquery
                ORDER BY id ASC
                """,
                (note_id, stmt_offset, stmt_limit),
            ) as r,
        ):
            comments: list[NoteComment] = await r.fetchall()  # type: ignore

            # Skip the header comment
            if skip_header and page == 1 and comments and comments[0]['event'] == 'opened':
                return comments[1:]

            return comments

    @staticmethod
    async def resolve_num_comments(notes: list[Note]) -> None:
        """Resolve the number of comments for each note."""
        if not notes:
            return

        id_map = {note['id']: note for note in notes}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT c.value, (
                    SELECT COUNT(*) FROM note_comment
                    WHERE note_id = c.value
                ) FROM unnest(%s) AS c(value)
                """,
                (list(id_map),),
            ) as r,
        ):
            for note_id, count in await r.fetchall():
                id_map[note_id]['num_comments'] = count

    @staticmethod
    async def resolve_comments(
        notes: list[Note],
        *,
        per_note_sort: Literal['asc', 'desc'] = 'desc',
        per_note_limit: int | None = None,
    ) -> list[NoteComment]:
        """Resolve comments for notes. Returns the resolved comments."""
        if not notes:
            return []

        id_map: dict[NoteId, list[NoteComment]] = {}
        for note in notes:
            id_map[note['id']] = note['comments'] = []

        query: Query
        params: Params
        if per_note_limit is not None:
            # Using window functions to limit comments per note
            query = SQL("""
            WITH ranked_comments AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY note_id ORDER BY id {}) AS _row_number
                FROM note_comment
                WHERE note_id = ANY(%s)
            )
            SELECT * FROM ranked_comments
            WHERE _row_number <= %s
            ORDER BY note_id, id
            """).format(SQL(per_note_sort))
            params = (list(id_map), per_note_limit)
        else:
            # Without limit, just fetch all comments
            query = """
            SELECT * FROM note_comment
            WHERE note_id = ANY(%s)
            ORDER BY note_id, id
            """
            params = (list(id_map),)

        async with db() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            comments: list[NoteComment] = await r.fetchall()  # type: ignore

        current_note_id: NoteId | None = None
        current_comments: list[NoteComment] = []

        for comment in comments:
            note_id = comment['note_id']
            if current_note_id != note_id:
                current_note_id = note_id
                current_comments = id_map[note_id]
            current_comments.append(comment)

        if per_note_limit is None:
            for note in notes:
                note['num_comments'] = len(note['comments'])  # pyright: ignore [reportTypedDictNotRequiredAccess]

        return comments
