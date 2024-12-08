from asyncio import TaskGroup
from collections.abc import Collection, Iterable, Sequence
from typing import Literal

import cython
from shapely.geometry.base import BaseGeometry
from sqlalchemy import Select, func, select, text, union_all

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.options_context import apply_options_context
from app.lib.standard_pagination import standard_pagination_range
from app.limits import NOTE_COMMENTS_PAGE_SIZE
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment, NoteEvent


class NoteCommentQuery:
    @staticmethod
    async def legacy_find_many_by_query(
        *,
        geometry: BaseGeometry | None = None,
        limit: int | None,
    ) -> Sequence[NoteComment]:
        """
        Find note comments by query.
        """
        async with db() as session:
            stmt = select(NoteComment)
            stmt = apply_options_context(stmt)
            where_and = [Note.visible_to(auth_user())]

            if geometry is not None:
                where_and.append(func.ST_Intersects(Note.point, func.ST_GeomFromText(geometry.wkt, 4326)))

            stmt = stmt.where(*where_and).order_by(NoteComment.id.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_comments_page(note_id: int, page: int, num_items: int) -> Sequence[NoteComment]:
        """
        Get comments for the given note comments page.

        The header comment is omitted.
        """
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=NOTE_COMMENTS_PAGE_SIZE,
            num_items=num_items,
        )
        async with db() as session:
            stmt = (
                select(NoteComment)
                .where(NoteComment.note_id == note_id)
                .order_by(NoteComment.id.desc())
                .offset(stmt_offset)
                .limit(stmt_limit)
            )
            stmt = apply_options_context(stmt)
            comments = (await session.scalars(stmt)).all()
        if page == 1 and comments and comments[-1].event == NoteEvent.opened:
            comments = comments[:-1]
        return comments[::-1]

    @staticmethod
    async def resolve_num_comments(notes: Iterable[Note]) -> None:
        """
        Resolve the number of comments for each note.
        """
        note_id_map = {note.id: note for note in notes}
        if not note_id_map:
            return

        async with db() as session:
            subq = (
                select(NoteComment.note_id)
                .where(NoteComment.note_id.in_(text(','.join(map(str, note_id_map)))))
                .subquery()
            )
            stmt = (
                select(subq.c.note_id, func.count())  #
                .select_from(subq)
                .group_by(subq.c.note_id)
            )
            rows: Sequence[tuple[int, int]] = (await session.execute(stmt)).all()  # pyright: ignore[reportAssignmentType]
            id_num_map: dict[int, int] = dict(rows)

        for note_id, note in note_id_map.items():
            note.num_comments = id_num_map.get(note_id, 0)

    @staticmethod
    async def resolve_comments(
        notes: Collection[Note],
        *,
        per_note_sort: Literal['asc', 'desc'] = 'desc',
        per_note_limit: int | None,
        resolve_rich_text: bool = True,
    ) -> Sequence[NoteComment]:
        """
        Resolve comments for notes.
        """
        if not notes:
            return ()
        id_comments_map: dict[int, list[NoteComment]] = {}
        for note in notes:
            id_comments_map[note.id] = note.comments = []

        async with db() as session:
            stmts: list[Select] = [None] * len(notes)  # type: ignore
            i: cython.int
            for i, note in enumerate(notes):
                stmt_ = select(NoteComment.id).where(
                    NoteComment.note_id == note.id,
                    NoteComment.created_at <= note.updated_at,
                )
                if per_note_limit is not None:
                    subq = (
                        stmt_.order_by(NoteComment.id.asc() if per_note_sort == 'asc' else NoteComment.id.desc())
                        .limit(per_note_limit)
                        .subquery()
                    )
                    stmt_ = select(subq.c.id).select_from(subq)
                stmts[i] = stmt_

            stmt = (
                select(NoteComment)
                .where(NoteComment.id.in_(union_all(*stmts).subquery().select()))
                .order_by(NoteComment.id.asc())
            )
            stmt = apply_options_context(stmt)
            comments: Sequence[NoteComment] = (await session.scalars(stmt)).all()

        current_note_id: int = 0
        current_comments: list[NoteComment] = []
        for comment in comments:
            note_id = comment.note_id
            if current_note_id != note_id:
                current_note_id = note_id
                current_comments = id_comments_map[note_id]
            current_comments.append(comment)

        if per_note_limit is None:
            for note in notes:
                note.num_comments = len(note.comments)

        if resolve_rich_text:
            async with TaskGroup() as tg:
                for comment in comments:
                    tg.create_task(comment.resolve_rich_text())

        return comments
