from app.lib.exceptions_context import raise_for
from app.lib.storage import AVATAR_STORAGE, BACKGROUND_STORAGE
from app.models.types import StorageKey, UserId
from app.queries.gravatar_query import GravatarQuery
from app.queries.user_query import UserQuery


class ImageQuery:
    @staticmethod
    async def get_gravatar(user_id: UserId) -> bytes:
        """Get a user's gravatar image.r"""
        user = await UserQuery.find_one_by_id(user_id)
        if user is None:
            raise_for.user_not_found(user_id)
        if user['avatar_type'] != 'gravatar':
            raise_for.image_not_found()
        return await GravatarQuery.load(user['email'])

    @staticmethod
    async def get_avatar(avatar_id: StorageKey) -> bytes:
        """Get a custom avatar image."""
        try:
            return await AVATAR_STORAGE.load(avatar_id)
        except FileNotFoundError:
            raise_for.image_not_found()

    @staticmethod
    async def get_background(background_id: StorageKey) -> bytes:
        """Get a custom background image."""
        try:
            return await BACKGROUND_STORAGE.load(background_id)
        except FileNotFoundError:
            raise_for.image_not_found()
