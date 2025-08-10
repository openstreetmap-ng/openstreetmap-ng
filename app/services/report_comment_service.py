import logging

from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user import UserRole
from app.models.types import ReportCommentId


class ReportCommentService:
    @staticmethod
    async def update_visibility(
        comment_id: ReportCommentId,
        new_visibility: UserRole,
    ) -> None:
        user = auth_user(required=True)
        user_id = user['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE report_comment SET visible_to = %s
                WHERE id = %s AND visible_to != %s
                """,
                (new_visibility, comment_id, new_visibility),
            )

            if result.rowcount:
                logging.debug(
                    'Changed visibility of comment %d to %r by user %d',
                    comment_id,
                    new_visibility,
                    user_id,
                )
