from io import BytesIO

import cython
from anyio import Path
from PIL import Image, ImageOps

from app.libc.exceptions_context import raise_for
from app.limits import AVATAR_MAX_FILE_SIZE, AVATAR_MAX_MEGAPIXELS, AVATAR_MAX_RATIO
from app.models.avatar_type import AvatarType

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')


class Avatar:
    @staticmethod
    def get_url(avatar_type: AvatarType, avatar_id: str | int) -> str:
        """
        Get the url of the avatar image.
        """

        if avatar_type == AvatarType.default:
            return '/static/img/avatar.webp'
        elif avatar_type == AvatarType.gravatar:
            return f'/api/web/avatar/gravatar/{avatar_id}'
        elif avatar_type == AvatarType.custom:
            return f'/api/web/avatar/custom/{avatar_id}'
        else:
            raise NotImplementedError(f'Unsupported avatar type {avatar_type!r}')

    @staticmethod
    async def get_default_image() -> bytes:
        """
        Get the default avatar image.
        """

        return await Path('app/static/img/avatar.webp').read_bytes()

    @staticmethod
    def normalize_image(data: bytes) -> bytes:
        """
        Normalize the avatar image.

        - Orientation: rotate
        - Shape ratio: crop
        - Megapixels: downscale
        - File size: reduce quality
        """

        img = Image.open(BytesIO(data))

        # normalize orientation
        ImageOps.exif_transpose(img, in_place=True)

        # normalize shape ratio
        img_width: cython.int = img.width
        img_height: cython.int = img.height
        ratio: cython.double = img_width / img_height

        # image is too wide
        if ratio > AVATAR_MAX_RATIO:
            new_width: cython.int = int(img_height * AVATAR_MAX_RATIO)
            x1: cython.int = (img_width - new_width) // 2
            x2: cython.int = (img_width + new_width) // 2
            img = img.crop((x1, 0, x2, img_height))
            img_width: cython.int = img.width

        # image is too tall
        elif ratio < 1 / AVATAR_MAX_RATIO:
            new_height: cython.int = int(img_width / AVATAR_MAX_RATIO)
            y1: cython.int = (img_height - new_height) // 2
            y2: cython.int = (img_height + new_height) // 2
            img = img.crop((0, y1, img_width, y2))
            img_height: cython.int = img.height

        # normalize megapixels
        mp_ratio: cython.double = (img_width * img_height) / AVATAR_MAX_MEGAPIXELS
        if mp_ratio > 1:
            img_width: cython.int = int(img_width / mp_ratio)
            img_height: cython.int = int(img_height / mp_ratio)
            img.thumbnail((img_width, img_height))

        # normalize file size
        with BytesIO() as buffer:
            for quality in (95, 90, 80, 70, 60, 50):
                buffer.seek(0)
                buffer.truncate()

                img.save(buffer, format='WEBP', quality=quality)

                if buffer.tell() <= AVATAR_MAX_FILE_SIZE:
                    return buffer.getvalue()

        raise_for().avatar_too_big()
