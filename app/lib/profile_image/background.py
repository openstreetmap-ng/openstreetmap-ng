from app.lib.profile_image.base import ProfileImageBase


class Background(ProfileImageBase):
    # TODO: specify min/max ratio, max megapixels, max file size

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
