from fastapi import UploadFile

from app.lib.avatar import Avatar
from app.lib.storage.base import StorageKey
from app.storage import AVATAR_STORAGE


class AvatarService:
    @staticmethod
    async def upload(file: UploadFile) -> StorageKey:
        """
        Process upload of a custom avatar image.

        Returns the avatar id.
        """
        data = await file.read()
        data = Avatar.normalize_image(data)
        avatar_id = await AVATAR_STORAGE.save(data, '.webp')
        return avatar_id

    @staticmethod
    async def delete_by_id(avatar_id: StorageKey) -> None:
        """
        Delete a custom avatar image by id.
        """
        await AVATAR_STORAGE.delete(avatar_id)
