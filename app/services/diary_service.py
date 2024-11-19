from shapely import Point
from sqlalchemy import delete, func, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.models.db.diary import Diary
from app.models.types import LocaleCode


class DiaryService:
    @staticmethod
    async def create(
        *,
        title: str,
        body: str,
        language: LocaleCode,
        point: Point | None,
    ) -> int:
        """
        Post a new diary entry.

        Returns the diary id.
        """
        async with db_commit() as session:
            diary = Diary(
                user_id=auth_user(required=True).id,
                title=title,
                body=body,
                language=language,
                point=point,
            )
            session.add(diary)
        return diary.id

    @staticmethod
    async def update(
        *,
        diary_id: int,
        title: str,
        body: str,
        language: LocaleCode,
        point: Point | None,
    ) -> None:
        """
        Update a diary entry.
        """
        async with db_commit() as session:
            stmt = (
                update(Diary)
                .where(
                    Diary.id == diary_id,
                    Diary.user_id == auth_user(required=True).id,
                )
                .values(
                    {
                        Diary.title: title,
                        Diary.body: body,
                        Diary.language: language,
                        Diary.point: point,
                        Diary.updated_at: func.statement_timestamp(),
                    }
                )
            )
            await session.execute(stmt)

    @staticmethod
    async def delete(diary_id: int) -> None:
        """
        Delete a diary entry.
        """
        async with db_commit() as session:
            stmt = delete(Diary).where(
                Diary.id == diary_id,
                Diary.user_id == auth_user(required=True).id,
            )
            await session.execute(stmt)
