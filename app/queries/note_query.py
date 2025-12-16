from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Literal

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
from shapely.geometry.base import BaseGeometry

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment, NoteEvent
from app.models.db.user import user_is_moderator
from app.models.types import NoteId, UserId


class NoteQuery:
    @staticmethod
    def user_page_where(
        user_id: UserId,
        *,
        commented_other: bool,
        open: bool | None,
    ) -> tuple[Composable, tuple[Any, ...]]:
        conditions: list[Composable] = []
        params: list[Any] = []

        if commented_other:
            # Notes where user commented but didn't open them.
            conditions.append(
                SQL("""
                    EXISTS (
                        SELECT 1 FROM note_comment
                        WHERE note_id = note.id
                        AND user_id = %s
                        AND event = 'commented'
                    )
                """)
            )
            conditions.append(
                SQL("""
                    NOT EXISTS (
                        SELECT 1 FROM note_comment
                        WHERE note_id = note.id
                        AND user_id = %s
                        AND event = 'opened'
                    )
                """)
            )
            params.extend((user_id, user_id))
        else:
            # Notes opened by the user.
            conditions.append(
                SQL("""
                    EXISTS (
                        SELECT 1 FROM note_comment
                        WHERE note_id = note.id
                        AND user_id = %s
                        AND event = 'opened'
                    )
                """)
            )
            params.append(user_id)

        # Only show hidden notes to moderators.
        if not user_is_moderator(auth_user()):
            conditions.append(SQL('hidden_at IS NULL'))

        if open is not None:
            conditions.append(
                SQL('closed_at IS NULL' if open else 'closed_at IS NOT NULL')
            )

        where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')
        return where_clause, tuple(params)

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
        where_clause, params = NoteQuery.user_page_where(
            user_id,
            commented_other=commented_other,
            open=open,
        )
        query = SQL('SELECT COUNT(*) FROM note WHERE {}').format(where_clause)

        async with db() as conn, await conn.execute(query, params) as r:
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def find(
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
            condition=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),
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
