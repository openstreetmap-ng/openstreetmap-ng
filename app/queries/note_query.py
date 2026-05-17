from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

from shapely.geometry.base import BaseGeometry

from app.db import db_count, db_fetchall, db_fetchone, db_fetchrows, t_and, t_order
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
        if commented_other:
            # Notes where user commented but didn't open them.
            interaction_cond = t"""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                    AND event = 'commented'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                    AND event = 'opened'
                )
            """
        else:
            # Notes opened by the user.
            interaction_cond = t"""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                    AND event = 'opened'
                )
            """

        return t_and(
            interaction_cond,
            # Only show hidden notes to moderators.
            t'hidden_at IS NULL' if not user_is_moderator(auth_user()) else None,
            t'({open}::bool IS NULL OR (closed_at IS NULL) = {open})',
        )

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
        return await db_count('note', where=where)

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
        sort_by_col = (
            'id'
            # Optimize query plan when not filtering by date
            if sort_by == 'created_at' and date_from is None and date_to is None
            else sort_by
        )

        phrase_cond = (
            t"""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND to_tsvector('simple', body) @@ phraseto_tsquery({phrase})
                )
            """
            if phrase is not None
            else None
        )

        if event is not None:
            assert user_id is not None, 'user_id must be set if event is set'
            user_cond = t"""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                    AND event = {event}
                )
            """
        elif user_id is not None:
            user_cond = t"""
                EXISTS (
                    SELECT 1 FROM note_comment
                    WHERE note_id = note.id
                    AND user_id = {user_id}
                )
            """
        else:
            user_cond = None

        if max_closed_days is not None:
            if max_closed_days > 0:
                cutoff = utcnow() - timedelta(days=max_closed_days)
                closed_cond = t'(closed_at IS NULL OR closed_at >= {cutoff})'
            else:
                closed_cond = t'closed_at IS NULL'
        else:
            closed_cond = None

        where = t_and(
            # Only show hidden notes to moderators
            t'hidden_at IS NULL' if not user_is_moderator(auth_user()) else None,
            phrase_cond,
            user_cond,
            t'id = ANY({note_ids})' if note_ids is not None else None,
            closed_cond,
            t'point && {geometry}' if geometry is not None else None,
            t'{sort_by_col:i} >= {date_from}' if date_from is not None else None,
            t'{sort_by_col:i} < {date_to}' if date_to is not None else None,
        )
        order_dir = t_order(sort_dir)

        return await db_fetchall(
            Note,
            t"""
                SELECT * FROM note
                WHERE {where:q}
                ORDER BY {sort_by_col:i} {order_dir:q}
            """,
            limit=limit,
        )

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
        where = t_and(
            # Only show hidden notes to moderators
            t'note.hidden_at IS NULL' if not user_is_moderator(auth_user()) else None,
            t'note.point && {geometry}' if geometry is not None else None,
        )

        return await db_fetchall(
            NoteComment,
            t"""
                SELECT * FROM note_comment
                JOIN note ON note_id = note.id
                WHERE {where:q}
                ORDER BY id DESC
            """,
            limit=limit,
        )

    @staticmethod
    async def find_header(note_id: NoteId) -> NoteComment | None:
        return await db_fetchone(
            NoteComment,
            t"""
                SELECT * FROM note_comment
                WHERE note_id = {note_id}
                ORDER BY id
                LIMIT 1
            """,
        )

    @staticmethod
    async def resolve_num_comments(notes: list[Note]) -> None:
        """Resolve the number of comments for each note."""
        if not notes:
            return

        id_map = {note['id']: note for note in notes}
        ids = list(id_map)

        rows = await db_fetchrows(t"""
            SELECT c.value, (
                SELECT COUNT(*) FROM note_comment
                WHERE note_id = c.value
            ) FROM unnest({ids}) AS c(value)
        """)
        for note_id, count in rows:
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
        ids = list(id_map)

        if per_note_limit is not None:
            sort_sql = t_order(per_note_sort)
            query = t"""
                WITH ranked_comments AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY note_id ORDER BY id {sort_sql:q}) AS rn
                    FROM note_comment
                    WHERE note_id = ANY({ids})
                )
                SELECT * FROM ranked_comments
                WHERE rn <= {per_note_limit}
                ORDER BY note_id, id
            """
        else:
            query = t"""
                SELECT * FROM note_comment
                WHERE note_id = ANY({ids})
                ORDER BY note_id, id
            """

        comments = await db_fetchall(NoteComment, query)

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
