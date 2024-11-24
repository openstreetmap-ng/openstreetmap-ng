import logging

from shapely import Point
from sqlalchemy import delete, select

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.models.db.diary import Diary
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.types import LocaleCode
from app.services.user_subscription_service import UserSubscriptionService


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
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            diary = Diary(
                user_id=user_id,
                title=title,
                body=body,
                language=language,
                point=point,
            )
            session.add(diary)
        diary_id = diary.id
        logging.debug('Created diary %d by user %d', diary_id, user_id)
        await UserSubscriptionService.subscribe(UserSubscriptionTarget.diary, diary_id)
        return diary_id

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
                select(Diary)
                .where(
                    Diary.id == diary_id,
                    Diary.user_id == auth_user(required=True).id,
                )
                .with_for_update()
            )
            diary = await session.scalar(stmt)
            if diary is None:
                return
            # prevent unnecessary updates
            if (
                diary.title != title  #
                or diary.body != body
                or diary.language != language
                or diary.point != point
            ):
                diary.title = title
                diary.body = body
                diary.language = language
                diary.point = point

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
