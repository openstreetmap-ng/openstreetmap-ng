from app.db import db_fetchone
from app.models.db.user_profile import UserProfile, user_profiles_resolve_rich_text
from app.models.types import UserId


class UserProfileQuery:
    @staticmethod
    async def get_by_user_id(
        user_id: UserId, *, resolve_rich_text: bool = True
    ) -> UserProfile:
        """Get a user profile by user id."""
        profile = await db_fetchone(
            UserProfile,
            t'SELECT * FROM user_profile WHERE user_id = {user_id}',
        )

        if profile is None:
            return {
                'user_id': user_id,
                'description': None,
                'description_rich_hash': None,
                'description_rich': '<p></p>',
                'socials': [],
            }

        if resolve_rich_text:
            await user_profiles_resolve_rich_text([profile])

            if 'description_rich' not in profile:
                profile['description_rich'] = '<p></p>'

        return profile
