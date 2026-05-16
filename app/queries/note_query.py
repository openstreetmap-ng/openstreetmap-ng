from collections import defaultdict
from datetime import datetime, timedelta
from string.templatelib import Template
from typing import Any, Literal

from psycopg.abc import Params, Query
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
from shapely.geometry.base import BaseGeometry

from app.db import db
from app.lib.auth.context import auth_user
from app.lib.time.date_utils import utcnow
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.db.user import user_is_moderator
from app.models.proto.note_types import GetCommentsResponse_Comment_Event
from app.models.types import NoteId, UserId


class NoteQuery:
    @staticmethod
    def user_page_where(
        user_id: UserId,
        *,
        commented_other: bool,
        open: bool | None,
    ):
        filters: list[Template] = []

        if commented_other:
            # Notes where user commented but didn't open them.
            filters.append(t"""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                    AND event = 'commented'
                )
            """)
            filters.append(t"""
                NOT EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                    AND event = 'opened'
                )
            """)
        else:
            # Notes opened by the user.
            filters.append(t"""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                    AND event = 'opened'
                )
            """)

        # Only show hidden notes to moderators.
        if not user_is_moderator(auth_user()):
            filters.append(t'hidden_at IS NULL')

        filters.append(t'({open}::bool IS NULL OR (closed_at IS NULL) = {open})')

        return SQL(' AND ').join(filters)

    @staticmethod
    async def count_by_user(
        user_id: UserId,
        *,
        commented_other: bool = False,
        open: bool | None = None,
    ) -> int:
        """
        Count the notes interacted with by the given user.
        If commented_other is True, it will count activity on non-own notes.
        """
        where = NoteQuery.user_page_where(
            user_id,
            commented_other=commented_other,
            open=open,
        )

        async with (
            db() as conn,
            await conn.execute(t'SELECT COUNT(*) FROM note WHERE {where:q}') as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find(
        *,
        phrase: str | None = None,
        user_id: UserId | None = None,
        event: GetCommentsResponse_Comment_Event | None = None,
        note_ids: list[NoteId] | None = None,
        max_closed_days: float | None = None,
        geometry: BaseGeometry | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: Literal['created_at', 'updated_at'] = 'created_at',
        sort_dir: Literal['asc', 'desc'] = 'desc',
        limit: int | None,
    ) -> list[Note]:
        """Find notes by query."""
        sort_by_identifier = Identifier(
            'id'
            # Optimize query plan when not filtering by date
            if sort_by == 'created_at' and date_from is None and date_to is None
            else sort_by
        )
        conditions: list[Composable] = []
        params: list[Any] = []

        # Only show hidden notes to moderators
        if not user_is_moderator(auth_user()):
            conditions.append(SQL('hidden_at IS NULL'))

        if phrase is not None:
            conditions.append(
                SQL("""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND to_tsvector('simple', body) @@ phraseto_tsquery(%s)
                )
                """)
            )
            params.append(phrase)

        if event is not None:
            assert user_id is not None, 'user_id must be set if event is set'
            conditions.append(
                SQL("""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = %s
                    AND event = %s
                )
                """)
            )
            params.extend((user_id, event))
        elif user_id is not None:
            conditions.append(
                SQL("""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = %s
                )
                """)
            )
            params.append(user_id)

        if note_ids is not None:
            conditions.append(SQL('id = ANY(%s)'))
            params.append(note_ids)

        if max_closed_days is not None:
            if max_closed_days > 0:
                conditions.append(SQL('(closed_at IS NULL OR closed_at >= %s)'))
                params.append(utcnow() - timedelta(days=max_closed_days))
            else:
                conditions.append(SQL('closed_at IS NULL'))

        if geometry is not None:
            conditions.append(SQL('point && %s'))
            params.append(geometry)

        if date_from is not None:
            conditions.append(SQL('{} >= %s').format(sort_by_identifier))
            params.append(date_from)

        if date_to is not None:
            conditions.append(SQL('{} < %s').format(sort_by_identifier))
            params.append(date_to)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        # Build the query with all conditions
        query = SQL("""
            SELECT * FROM note
            WHERE {condition}
            ORDER BY {order_by} {order_dir}
            {limit}
        """).format(
            condition=SQL(' AND ').join(conditions or (SQL('TRUE'),)),
            order_by=sort_by_identifier,
            order_dir=SQL(sort_dir),
            limit=limit_clause,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_legacy_note(comments: list[NoteComment]) -> None:
        """Resolve legacy note fields for the given comments."""
        if not comments:
            return

        id_map = defaultdict[NoteId, list[NoteComment]](list)
        for comment in comments:
            id_map[comment['note_id']].append(comment)

        notes = await NoteQuery.find(note_ids=list(id_map), limit=len(id_map))
        for note in notes:
            for comment in id_map[note['id']]:
                comment['legacy_note'] = note


# === Note Comments ===


class NoteCommentQuery:
    @staticmethod
    async def legacy_find(
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
            conditions.append(SQL('note.point && %s'))
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
            conditions=SQL(' AND ').join(conditions or (SQL('TRUE'),)),
            limit=limit_clause,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_header(note_id: NoteId) -> NoteComment | None:
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM note_comment
                WHERE note_id = %s
                ORDER BY id
                LIMIT 1
                """,
                (note_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

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
                SELECT *, ROW_NUMBER() OVER (PARTITION BY note_id ORDER BY id {}) AS rn
                FROM note_comment
                WHERE note_id = ANY(%s)
            )
            SELECT * FROM ranked_comments
            WHERE rn <= %s
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

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
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
