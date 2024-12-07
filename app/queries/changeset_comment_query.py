from asyncio import TaskGroup
from collections.abc import Collection, Iterable, Sequence

import cython
from sqlalchemy import Select, func, select, text, union_all

from app.db import db
from app.lib.options_context import apply_options_context
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment


class ChangesetCommentQuery:
    @staticmethod
    async def resolve_num_comments(changesets: Iterable[Changeset]) -> None:
        """
        Resolve the number of comments for each changeset.
        """
        changeset_id_map = {changeset.id: changeset for changeset in changesets}
        if not changeset_id_map:
            return

        async with db() as session:
            subq = (
                select(ChangesetComment.changeset_id)
                .where(ChangesetComment.changeset_id.in_(text(','.join(map(str, changeset_id_map)))))
                .subquery()
            )
            stmt = (
                select(subq.c.changeset_id, func.count())  #
                .select_from(subq)
                .group_by(subq.c.changeset_id)
            )
            rows: Sequence[tuple[int, int]] = (await session.execute(stmt)).all()  # pyright: ignore[reportAssignmentType]
            id_num_map: dict[int, int] = dict(rows)

        for changeset_id, changeset in changeset_id_map.items():
            changeset.num_comments = id_num_map.get(changeset_id, 0)

    @staticmethod
    async def resolve_comments(
        changesets: Collection[Changeset],
        *,
        limit_per_changeset: int | None,
        resolve_rich_text: bool = True,
    ) -> None:
        """
        Resolve comments for changesets.
        """
        if not changesets:
            return
        id_comments_map: dict[int, list[ChangesetComment]] = {}
        for changeset in changesets:
            id_comments_map[changeset.id] = changeset.comments = []

        async with db() as session:
            stmts: list[Select] = [None] * len(changesets)  # type: ignore
            i: cython.int
            for i, changeset in enumerate(changesets):
                stmt_ = select(ChangesetComment.id).where(
                    ChangesetComment.changeset_id == changeset.id,
                    ChangesetComment.created_at <= changeset.updated_at,
                )
                if limit_per_changeset is not None:
                    subq = (
                        stmt_.order_by(ChangesetComment.created_at.desc())
                        .limit(limit_per_changeset)  #
                        .subquery()
                    )
                    stmt_ = select(subq.c.id).select_from(subq)
                stmts[i] = stmt_

            stmt = (
                select(ChangesetComment)
                .where(ChangesetComment.id.in_(union_all(*stmts).subquery().select()))
                .order_by(ChangesetComment.created_at.asc())
            )
            stmt = apply_options_context(stmt)
            comments = (await session.scalars(stmt)).all()

        current_changeset_id: int = 0
        current_comments: list[ChangesetComment] = []
        for comment in comments:
            changeset_id = comment.changeset_id
            if current_changeset_id != changeset_id:
                current_changeset_id = changeset_id
                current_comments = id_comments_map[changeset_id]
            current_comments.append(comment)

        for changeset in changesets:
            changeset.num_comments = len(changeset.comments)  # pyright: ignore[reportArgumentType]

        if resolve_rich_text:
            async with TaskGroup() as tg:
                for comment in comments:
                    tg.create_task(comment.resolve_rich_text())
