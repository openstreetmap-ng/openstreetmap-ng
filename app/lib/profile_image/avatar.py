from enum import Enum
from pathlib import Path
from typing import override

from app.lib.profile_image.base import ProfileImageBase
from app.limits import AVATAR_MAX_FILE_SIZE, AVATAR_MAX_MEGAPIXELS, AVATAR_MAX_RATIO


class AvatarType(str, Enum):
    default = 'default'
    gravatar = 'gravatar'
    custom = 'custom'


class Avatar(ProfileImageBase):
    default_image: bytes = Path('app/static/img/avatar.webp').read_bytes()

    min_ratio = 1 / AVATAR_MAX_RATIO
    max_ratio = AVATAR_MAX_RATIO
    max_megapixels = AVATAR_MAX_MEGAPIXELS
    max_file_size = AVATAR_MAX_FILE_SIZE

    @override
    @staticmethod
    def get_url(image_type: AvatarType, image_id: str | int | None) -> str:
        """
        Get the url of the avatar image.

        >>> Avatar.get_url(AvatarType.custom, '123456')
        '/api/web/avatar/custom/123456'
        """
        if image_type == AvatarType.default:
            return '/static/img/avatar.webp'
        elif image_type == AvatarType.gravatar:
            return f'/api/web/avatar/gravatar/{image_id}'
        elif image_type == AvatarType.custom:
            return f'/api/web/avatar/custom/{image_id}'
        else:
            raise NotImplementedError(f'Unsupported avatar type {image_type!r}')
