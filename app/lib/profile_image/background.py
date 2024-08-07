from pathlib import Path

from app.lib.profile_image.base import ProfileImageBase


class Background(ProfileImageBase):
    default_image: bytes = Path(
        'app/static/img/avatar.webp'
    ).read_bytes()  # TODO: there should be no default background

    # TODO: specify min/max ratio, max megapixels, max file size

    # TODO: replace avatar requests with background ones
    @staticmethod
    def get_url(image_id: str | int | None) -> str:
        """
        Get the url of the avatar image.

        >>> Background.get_url('123456')
        '/api/web/avatar/custom/123456'
        """

        if image_id is not None:
            return f'/api/web/avatar/custom/{image_id}'
        else:
            return '/static/img/avatar.webp'
