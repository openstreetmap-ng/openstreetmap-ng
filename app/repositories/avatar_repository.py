from app.lib.storage import AVATAR_STORAGE, GRAVATAR_STORAGE
from app.lib_cython.exceptions_context import raise_for
from app.repositories.user_repository import UserRepository


class AvatarRepository:
    @staticmethod
    async def get_gravatar(user_id: int) -> bytes:
        """
        Get a user's gravatar image.
        """

        user = await UserRepository.find_one_by_id(user_id)

        if not user:
            raise_for().user_not_found(user_id)

        file = await GRAVATAR_STORAGE.load(user.email)
        return file

    @staticmethod
    async def get_custom(avatar_id: str) -> bytes:
        """
        Get a custom avatar image.
        """

        try:
            file = await AVATAR_STORAGE.load(avatar_id)
        except FileNotFoundError:
            raise_for().avatar_not_found(avatar_id)

        return file
