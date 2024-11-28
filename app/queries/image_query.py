from app.lib.exceptions_context import raise_for
from app.lib.image import AvatarType
from app.models.types import StorageKey
from app.queries.user_query import UserQuery
from app.storage import AVATAR_STORAGE, BACKGROUND_STORAGE, GRAVATAR_STORAGE


class ImageQuery:
    @staticmethod
    async def get_gravatar(user_id: int) -> bytes:
        """
        Get a user's gravatar image.r
        """
        user = await UserQuery.find_one_by_id(user_id)
        if user is None:
            raise_for.user_not_found(user_id)
        if user.avatar_type != AvatarType.gravatar:
            raise_for.image_not_found()
        return await GRAVATAR_STORAGE.load(user.email)

    @staticmethod
    async def get_avatar(avatar_id: StorageKey) -> bytes:
        """
        Get a custom avatar image.
        """
        try:
            return await AVATAR_STORAGE.load(avatar_id)
        except FileNotFoundError:
            raise_for.image_not_found()

    @staticmethod
    async def get_background(background_id: StorageKey) -> bytes:
        """
        Get a custom background image.
        """
        try:
            return await BACKGROUND_STORAGE.load(background_id)
        except FileNotFoundError:
            raise_for.image_not_found()
