from psycopg.rows import dict_row

from app.db import db
from app.models.db.user_profile import UserProfile, user_profiles_resolve_rich_text
from app.models.types import UserId


class UserProfileQuery:
    @staticmethod
    async def get_by_user_id(
        user_id: UserId, *, resolve_rich_text: bool = True
    ) -> UserProfile:
        """Get a user profile by user id."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM user_profile
                WHERE user_id = %s
                """,
                (user_id,),
            ) as r,
        ):
            profile: UserProfile | None = await r.fetchone()  # type: ignore

        if profile is None:
            return {
                'user_id': user_id,
                'description': '',
                'description_rich_hash': None,
                'description_rich': '<p></p>',
            }

        if resolve_rich_text:
            await user_profiles_resolve_rich_text([profile])

        return profile
