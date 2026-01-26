from app.lib.image import Image
from app.lib.storage import AVATAR_STORAGE, BACKGROUND_STORAGE


class ImageService:
    @staticmethod
    async def upload_avatar(data: bytes):
        """Process upload of a custom avatar image. Returns the avatar id."""
        data = await Image.normalize_avatar(data)
        return await AVATAR_STORAGE.save(data, '.webp')

    @staticmethod
    async def upload_background(data: bytes):
        """Process upload of a custom background image. Returns the background id."""
        data = await Image.normalize_background(data)
        return await BACKGROUND_STORAGE.save(data, '.webp')
