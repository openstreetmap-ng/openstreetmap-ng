from fastapi import UploadFile

from app.lib.profile_image.background import Background
from app.models.types import StorageKey
from app.storage import BACKGROUND_STORAGE


class BackgroundService:
    @staticmethod
    async def upload(file: UploadFile) -> StorageKey:
        """
        Process upload of a custom background image.

        Returns the background id.
        """
        data = await file.read()
        data = Background.normalize_image(data)
        background_id = await BACKGROUND_STORAGE.save(data, '.webp')
        return background_id

    @staticmethod
    async def delete_by_id(background_id: StorageKey) -> None:
        """
        Delete a custom background image by id.
        """
        await BACKGROUND_STORAGE.delete(background_id)
