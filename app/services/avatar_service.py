from fastapi import UploadFile

from app.lib.storage import AVATAR_STORAGE
from app.libc.avatar import Avatar


class AvatarService:
    @staticmethod
    async def process_upload(file: UploadFile) -> str:
        """
        Process upload of a custom avatar image.

        Returns the avatar id.
        """

        data = await file.read()
        data = Avatar.normalize_image(data)
        avatar_id = await AVATAR_STORAGE.save(data, '.webp', random=True)
        return avatar_id

    @staticmethod
    async def delete_by_id(avatar_id: str) -> None:
        """
        Delete a custom avatar image by id.
        """

        await AVATAR_STORAGE.delete(avatar_id)
