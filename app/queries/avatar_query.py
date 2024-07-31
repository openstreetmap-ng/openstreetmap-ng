from app.lib.exceptions_context import raise_for
from app.models.types import StorageKey
from app.queries.user_query import UserQuery
from app.storage import AVATAR_STORAGE, GRAVATAR_STORAGE


class AvatarQuery:
    @staticmethod
    async def get_gravatar(user_id: int) -> bytes:
        """
        Get a user's gravatar image.
        """
        user = await UserQuery.find_one_by_id(user_id)
        if user is None:
            raise_for().user_not_found(user_id)
        return await GRAVATAR_STORAGE.load(user.email)

    @staticmethod
    async def get_custom(avatar_id: StorageKey) -> bytes:
        """
        Get a custom avatar image.
        """
        try:
            return await AVATAR_STORAGE.load(avatar_id)
        except FileNotFoundError:
            raise_for().avatar_not_found(avatar_id)
