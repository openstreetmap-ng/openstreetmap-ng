from app.db import db
from app.lib.auth_context import auth_user
from app.models.db.user_profile import UserSocial


class UserProfileService:
    @staticmethod
    async def update_description(
        *,
        description: str,
    ) -> None:
        """Update user's profile description."""
        user_id = auth_user(required=True)['id']
        value = description.strip() or None

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO user_profile (user_id, description)
                VALUES (%(user_id)s, %(description)s)
                ON CONFLICT (user_id) DO UPDATE SET
                    description = EXCLUDED.description,
                    description_rich_hash = NULL
                WHERE user_profile.description IS DISTINCT FROM EXCLUDED.description
                """,
                {'user_id': user_id, 'description': value},
            )

    @staticmethod
    async def update_socials(
        *,
        socials: list[UserSocial],
    ) -> None:
        """Update user's social links."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO user_profile (user_id, socials)
                VALUES (%(user_id)s, %(socials)s)
                ON CONFLICT (user_id) DO UPDATE SET
                    socials = EXCLUDED.socials
                WHERE user_profile.socials != EXCLUDED.socials
                """,
                {'user_id': user_id, 'socials': socials},
            )
