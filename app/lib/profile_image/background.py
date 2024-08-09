from app.lib.profile_image.base import ProfileImageBase
from app.limits import BACKGROUND_MAX_FILE_SIZE, BACKGROUND_MAX_MEGAPIXELS, BACKGROUND_MAX_RATIO, BACKGROUND_MIN_RATIO


class Background(ProfileImageBase):
    min_ratio = BACKGROUND_MIN_RATIO
    max_ratio = BACKGROUND_MAX_RATIO
    max_megapixels = BACKGROUND_MAX_MEGAPIXELS
    max_file_size = BACKGROUND_MAX_FILE_SIZE

    @staticmethod
    def get_url(image_id: str | int | None) -> str | None:
        """
        Get the url of the background image.

        >>> Background.get_url('123456')
        '/api/web/background/custom/123456'
        """

        if image_id is not None:
            return f'/api/web/background/custom/{image_id}'
        else:
            return None
