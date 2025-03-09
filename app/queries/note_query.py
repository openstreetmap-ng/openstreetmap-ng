from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Literal

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
from shapely.geometry.base import BaseGeometry

from app.db import db2
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.standard_pagination import standard_pagination_range
from app.limits import NOTE_USER_PAGE_SIZE
from app.models.db.note import Note, NoteId
from app.models.db.note_comment import NoteComment, NoteEvent
from app.models.db.user import UserId, user_is_moderator


class NoteQuery:
    @staticmethod
    async def count_by_user_id(
        user_id: UserId,
        *,
        commented_other: bool = False,
        open: bool | None = None,
    ) -> int:
        """
        Count notes interacted with by user id.
        If commented_other is True, it will count activity on non-own notes.
        """
        conditions: list[Composable] = []
        params: list[Any] = []

        if commented_other:
            # Find notes where user commented but didn't open them
            query = SQL("""
                SELECT COUNT(DISTINCT note_id) FROM note_comment
                JOIN note ON note_id = note.id
                WHERE user_id = %s
                AND event = 'commented'
                AND NOT EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = %s
                    AND event = 'opened'
                )
            """)
            params.extend((user_id, user_id))
        else:
            # Find notes opened by the user
            query = SQL("""
                SELECT COUNT(*) FROM note_comment
                JOIN note ON note_id = note.id
                WHERE user_id = %s
                AND event = 'opened'
            """)
            params.append(user_id)

        # Only show hidden notes to moderators
        if not user_is_moderator(auth_user()):
            conditions.append(SQL('note.hidden_at IS NULL'))

        if open is not None:
            conditions.append(SQL('note.closed_at IS NULL') if open else SQL('note.closed_at IS NOT NULL'))

        # Add conditions to the query
        if conditions:
            query = SQL('{} AND {}').format(query, SQL(' AND ').join(conditions))

        async with db2() as conn, await conn.execute(query, params) as r:
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def get_user_notes_page(
        user_id: UserId,
        *,
        page: int,
        num_items: int,
        commented_other: bool,
        open: bool | None,
    ) -> list[Note]:
        """Get notes for the given user notes page."""
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=NOTE_USER_PAGE_SIZE,
            num_items=num_items,
        )

        conditions: list[Composable] = []
        params: list[Any] = []

        if commented_other:
            # Find notes where user commented but didn't open them
            query = SQL("""
                SELECT DISTINCT note.* FROM note_comment
                JOIN note ON note_id = note.id
                WHERE user_id = %s
                AND event = 'commented'
                AND NOT EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = %s
                    AND event = 'opened'
                )
            """)
            params.extend((user_id, user_id))
        else:
            # Find notes opened by the user
            query = SQL("""
                SELECT note.* FROM note_comment
                JOIN note ON note_id = note.id
                WHERE user_id = %s
                AND event = 'opened'
            """)
            params.append(user_id)

        # Only show hidden notes to moderators
        if not user_is_moderator(auth_user()):
            conditions.append(SQL('note.hidden_at IS NULL'))

        if open is not None:
            conditions.append(SQL('note.closed_at IS NULL') if open else SQL('note.closed_at IS NOT NULL'))

        # Add conditions to the query
        if conditions:
            query = SQL('{} AND {}').format(query, SQL(' AND ').join(conditions))

        # Add pagination and ordering
        # Get results in DESC order, then reverse for final result
        query = SQL("""
            SELECT * FROM (
                {}
                ORDER BY note.updated_at DESC
                OFFSET %s
                LIMIT %s
            ) ORDER BY updated_at ASC
        """).format(query)
        params.extend((stmt_offset, stmt_limit))

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_many_by_query(
        *,
        phrase: str | None = None,
        user_id: UserId | None = None,
        event: NoteEvent | None = None,
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
        sort_by_identifier = Identifier(sort_by)
        conditions: list[Composable] = []
        params: list[Any] = []

        # Only show hidden notes to moderators
        if not user_is_moderator(auth_user()):
            conditions.append(SQL('note.hidden_at IS NULL'))

        if phrase is not None:
            conditions.append(
                SQL("""
                note.id IN (
                    SELECT DISTINCT note_id
                    FROM note_comment
                    WHERE to_tsvector('simple', body) @@ phraseto_tsquery(%s)
                )
                """)
            )
            params.append(phrase)

        if user_id is not None:
            conditions.append(
                SQL("""
                note.id IN (
                    SELECT DISTINCT note_id
                    FROM note_comment
                    WHERE user_id = %s
                )
                """)
            )
            params.append(user_id)

        if event is not None:
            conditions.append(
                SQL("""
                note.id IN (
                    SELECT DISTINCT note_id
                    FROM note_comment
                    WHERE event = %s
                )
                """)
            )
            params.append(event)

        if note_ids is not None:
            conditions.append(SQL('note.id = ANY(%s)'))
            params.append(note_ids)

        if max_closed_days is not None:
            if max_closed_days > 0:
                conditions.append(SQL('(note.closed_at IS NULL OR note.closed_at >= %s)'))
                params.append(utcnow() - timedelta(days=max_closed_days))
            else:
                conditions.append(SQL('note.closed_at IS NULL'))

        if geometry is not None:
            conditions.append(SQL('ST_Intersects(note.point, %s)'))
            params.append(geometry)

        if date_from is not None:
            conditions.append(SQL('note.{} >= %s').format(sort_by_identifier))
            params.append(date_from)

        if date_to is not None:
            conditions.append(SQL('note.{} < %s').format(sort_by_identifier))
            params.append(date_to)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        # Build the query with all conditions
        query = SQL("""
            SELECT note.* FROM note
            WHERE {condition}
            ORDER BY note.{sort_by} {sort_dir}
            {limit}
        """).format(
            condition=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
            sort_by=sort_by_identifier,
            sort_dir=SQL(sort_dir),
            limit=limit_clause,
        )

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def resolve_legacy_note(comments: list[NoteComment]) -> None:
        """Resolve legacy note fields for the given comments."""
        if not comments:
            return

        id_map: dict[NoteId, list[NoteComment]] = defaultdict(list)
        for comment in comments:
            id_map[comment['note_id']].append(comment)

        notes = await NoteQuery.find_many_by_query(note_ids=list(id_map), limit=len(id_map))
        for note in notes:
            for comment in id_map[note['id']]:
                comment['legacy_note'] = note
