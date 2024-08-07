from app.lib.exceptions_context import raise_for
from app.models.types import StorageKey
from app.storage import BACKGROUND_STORAGE


class BackgroundQuery:
    @staticmethod
    async def get_custom(background_id: StorageKey) -> bytes:
        """
        Get a custom background image.
        """
        try:
            return await BACKGROUND_STORAGE.load(background_id)
        except FileNotFoundError:
            raise_for().background_not_found(background_id)
