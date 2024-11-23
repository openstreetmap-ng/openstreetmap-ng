from collections.abc import Iterable, Sequence

from sqlalchemy import func, select, text

from app.db import db
from app.lib.options_context import apply_options_context
from app.lib.standard_pagination import standard_pagination_range
from app.limits import DIARY_COMMENTS_PAGE_SIZE
from app.models.db.diary import Diary
from app.models.db.diary_comment import DiaryComment


class DiaryCommentQuery:
    @staticmethod
    async def get_diary_page(
        diary_id: int,
        *,
        page: int,
        num_comments: int,
    ) -> Sequence[DiaryComment]:
        """
        Get comments for the given diary page.
        """
        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=DIARY_COMMENTS_PAGE_SIZE,
            num_items=num_comments,
        )
        async with db() as session:
            stmt = (
                select(DiaryComment)
                .where(DiaryComment.diary_id == diary_id)
                .order_by(DiaryComment.created_at.asc())
                .offset(stmt_offset)
                .limit(stmt_limit)
            )
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()

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
