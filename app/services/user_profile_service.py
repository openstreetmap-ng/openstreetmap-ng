from app.db import db
from app.lib.auth_context import auth_user


class UserProfileService:
    @staticmethod
    async def update_description(
        *,
        description: str,
    ) -> None:
        """Update user's profile description."""
        user = auth_user(required=True)
        user_id = user['id']

        if not description:
            async with db(True) as conn:
                await conn.execute(
                    'DELETE FROM user_profile WHERE user_id = %s',
                    (user_id,),
                )
            return

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO user_profile (user_id, description)
                VALUES (%(user_id)s, %(description)s)
                ON CONFLICT (user_id) DO UPDATE SET
                    description = EXCLUDED.description,
                    description_rich_hash = NULL
                WHERE user_profile.description != EXCLUDED.description
                """,
                {'user_id': user_id, 'description': description},
            )
