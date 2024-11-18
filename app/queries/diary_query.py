from collections.abc import Sequence

from sqlalchemy import func, select, text

from app.db import db
from app.lib.options_context import apply_options_context
from app.models.db.diary import Diary
from app.models.types import LocaleCode


class DiaryQuery:
    @staticmethod
    async def find_one_by_id(diary_id: int) -> Diary | None:
        """
        Find a diary by id.
        """
        async with db() as session:
            stmt = select(Diary).where(Diary.id == diary_id)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def count_by_user_id(user_id: int) -> int:
        """
        Count diaries by user id.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(
                select(text('1'))
                .where(
                    Diary.user_id == user_id,
                )
                .subquery()
            )
            return (await session.execute(stmt)).scalar_one()

    @staticmethod
    async def find_many_recent(
        *,
        user_id: int | None = None,
        language: LocaleCode | None = None,
        after: int | None = None,
        before: int | None = None,
        limit: int,
    ) -> Sequence[Diary]:
        """
        Find recent diaries.
        """
        if user_id is not None and language is not None:
            # prevent accidental index miss
            raise AssertionError('user_id and language cannot be both set')
        async with db() as session:
            stmt = select(Diary)
            where_and = []

            if user_id is not None:
                where_and.append(Diary.user_id == user_id)
            if language is not None:
                where_and.append(Diary.language == language)

            if after is not None:
                where_and.append(Diary.id > after)
            if before is not None:
                where_and.append(Diary.id < before)

            stmt = stmt.where(*where_and)
            order_desc = (after is None) or (before is not None)
            stmt = stmt.order_by(Diary.id.desc() if order_desc else Diary.id.asc()).limit(limit)

            stmt = apply_options_context(stmt)
            rows = (await session.scalars(stmt)).all()
            return rows if order_desc else rows[::-1]
