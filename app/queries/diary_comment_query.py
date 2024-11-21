from asyncio import TaskGroup
from collections.abc import Collection, Iterable, Sequence

import cython
from sqlalchemy import Select, func, select, text, union_all

from app.db import db
from app.lib.options_context import apply_options_context
from app.models.db.diary import Diary
from app.models.db.diary_comment import DiaryComment


class DiaryCommentQuery:
    @staticmethod
    async def resolve_comments(
        diaries: Collection[Diary],
        *,
        limit_per_diary: int | None = None,
        resolve_rich_text: bool = True,
    ) -> None:
        """
        Resolve comments for diaries.
        """
        if not diaries:
            return
        id_diary_map: dict[int, Diary] = {diary.id: diary for diary in diaries}
        if not id_diary_map:
            return

        async with db() as session:
            stmts: list[Select] = [None] * len(diaries)  # pyright: ignore[reportAssignmentType]
            i: cython.int
            for i, diary in enumerate(diaries):
                stmt_ = select(DiaryComment.id).where(DiaryComment.diary_id == diary.id)
                if limit_per_diary is not None:
                    subq = (
                        stmt_.order_by(DiaryComment.created_at.asc())
                        .limit(limit_per_diary)  #
                        .subquery()
                    )
                    stmt_ = select(subq.c.id).select_from(subq)
                stmts[i] = stmt_

            stmt = (
                select(DiaryComment)
                .where(DiaryComment.id.in_(union_all(*stmts).subquery().select()))
                .order_by(DiaryComment.created_at.asc())
            )
            stmt = apply_options_context(stmt)
            comments = (await session.scalars(stmt)).all()

        current_diary_id: int = 0
        current_comments: list[DiaryComment] = []
        for comment in comments:
            diary_id = comment.diary_id
            if current_diary_id != diary_id:
                current_diary_id = diary_id
                current_comments = id_diary_map[diary_id].comments = []
            current_comments.append(comment)

        for diary in diaries:
            diary.num_comments = len(diary.comments)  # pyright: ignore[reportArgumentType]

        if resolve_rich_text:
            async with TaskGroup() as tg:
                for comment in comments:
                    tg.create_task(comment.resolve_rich_text())

    @staticmethod
    async def resolve_num_comments(diaries: Iterable[Diary]) -> None:
        """
        Resolve the number of comments for each changeset.
        """
        diary_id_map = {diary.id: diary for diary in diaries}
        if not diary_id_map:
            return

        async with db() as session:
            subq = (
                select(DiaryComment.diary_id)
                .where(DiaryComment.diary_id.in_(text(','.join(map(str, diary_id_map)))))
                .subquery()
            )
            stmt = (
                select(subq.c.diary_id, func.count())  #
                .select_from(subq)
                .group_by(subq.c.diary_id)
            )
            rows: Sequence[tuple[int, int]] = (await session.execute(stmt)).all()  # pyright: ignore[reportAssignmentType]
            id_num_map: dict[int, int] = dict(rows)

        for diary_id, diary in diary_id_map.items():
            diary.num_comments = id_num_map.get(diary_id, 0)
