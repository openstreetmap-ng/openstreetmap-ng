from collections.abc import Sequence

from anyio import create_task_group
from sqlalchemy import select, union_all

from app.db import db
from app.lib.statement_context import apply_statement_context
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment


class ChangesetCommentRepository:
    @staticmethod
    async def resolve_comments(
        changesets: Sequence[Changeset],
        *,
        limit_per_changeset: int | None,
        rich_text: bool = True,
    ) -> None:
        """
        Resolve comments for changesets.
        """
        # small optimization
        if not changesets:
            return

        async with db() as session:
            stmts = []

            for changeset in changesets:
                stmt_ = (
                    select(ChangesetComment.id)
                    .where(
                        ChangesetComment.changeset_id == changeset.id,
                        ChangesetComment.created_at <= changeset.updated_at,
                    )
                    .order_by(ChangesetComment.created_at.desc())
                )
                stmt_ = apply_statement_context(stmt_)

                if limit_per_changeset is not None:
                    stmt_ = stmt_.limit(limit_per_changeset)

                stmts.append(stmt_)

            stmt = (
                select(ChangesetComment)
                .where(ChangesetComment.id.in_(union_all(*stmts).subquery()))
                .order_by(ChangesetComment.created_at.desc())
            )
            stmt = apply_statement_context(stmt)

            comments: Sequence[ChangesetComment] = (await session.scalars(stmt)).all()

        id_comments_map: dict[int, list[ChangesetComment]] = {}
        for changeset in changesets:
            id_comments_map[changeset.id] = changeset.comments = []
        for comment in comments:
            id_comments_map[comment.changeset_id].append(comment)

        if rich_text:
            async with create_task_group() as tg:
                for comment in comments:
                    tg.start_soon(comment.resolve_rich_text)
