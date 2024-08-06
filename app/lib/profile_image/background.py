from enum import Enum
from pathlib import Path
from typing import override

from app.lib.profile_image.base import ProfileImageBase


class BackgroundType(str, Enum):
    default = 'default'
    custom = 'custom'


class Background(ProfileImageBase):
    default_image: bytes = Path(
        'app/static/img/avatar.webp'
    ).read_bytes()  # TODO: there should be no default background

    # TODO: specify min/max ratio, max megapixels, max file size

    # TODO: replace avatar requests with background ones
    @override
    @staticmethod
    def get_url(image_type: BackgroundType, image_id: str | int | None) -> str:
        """
        Get the url of the avatar image.

        >>> Avatar.get_url(BackgroundType.custom, '123456')
        '/api/web/avatar/custom/123456'
        """
        if image_type == BackgroundType.default:
            return '/static/img/avatar.webp'
        elif image_type == BackgroundType.custom:
            return f'/api/web/avatar/custom/{image_id}'
        else:
            raise NotImplementedError(f'Unsupported avatar type {image_type!r}')
