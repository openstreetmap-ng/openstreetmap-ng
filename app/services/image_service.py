from PIL.Image import DecompressionBombError

from app.config import AVATAR_UPLOAD_MAX_SIZE
from app.exceptions.context import raise_for
from app.lib.io.image import Image
from app.lib.storage import AVATAR_STORAGE, BACKGROUND_STORAGE


class ImageService:
    @staticmethod
    async def upload_avatar(data: bytes):
        """Process upload of a custom avatar image. Returns the avatar id."""
        if len(data) > AVATAR_UPLOAD_MAX_SIZE:
            raise_for.image_too_big()
        try:
            data = await Image.normalize_avatar(data)
        except DecompressionBombError:
            raise_for.image_too_big()
        except OSError:
            raise_for.image_invalid()
        return await AVATAR_STORAGE.save(data, '.webp')

    @staticmethod
    async def upload_background(data: bytes):
        """Process upload of a custom background image. Returns the background id."""
        data = await Image.normalize_background(data)
        return await BACKGROUND_STORAGE.save(data, '.webp')
