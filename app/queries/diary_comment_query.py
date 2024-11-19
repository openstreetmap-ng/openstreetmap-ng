from collections.abc import Iterable, Sequence

from sqlalchemy import func, select, text

from app.db import db
from app.models.db.diary import Diary
from app.models.db.diary_comment import DiaryComment


class DiaryCommentQuery:
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
