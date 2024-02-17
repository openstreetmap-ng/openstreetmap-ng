import logging
from io import BytesIO

import cython
from anyio import Path
from PIL import Image, ImageOps

from app.lib.exceptions_context import raise_for
from app.lib.naturalsize import naturalsize
from app.limits import AVATAR_MAX_FILE_SIZE, AVATAR_MAX_MEGAPIXELS, AVATAR_MAX_RATIO
from app.models.avatar_type import AvatarType


@cython.cfunc
def _optimize_quality(img: Image) -> tuple[int, bytes]:
    # read property once for performance
    max_size: int = AVATAR_MAX_FILE_SIZE
    size: int

    with BytesIO() as buffer:
        # lossless mode
        compression_level: int = 100

        img.save(buffer, format='WEBP', quality=compression_level, lossless=True)
        size = buffer.tell()
        logging.debug('Optimizing avatar quality (lossless): Q%d -> %s', compression_level, naturalsize(size))

        if size <= max_size:
            return compression_level, buffer.getvalue()

        high: cython.int = 95
        low: cython.int = 20
        bs_step: cython.int = 5
        best_quality: cython.int = -1
        best_buffer: bytes | None = None

        # initial quick scan
        quality: cython.int
        for quality in range(80, 20 - 1, -20):
            buffer.seek(0)
            buffer.truncate()

            img.save(buffer, format='WEBP', quality=quality)
            size = buffer.tell()
            logging.debug('Optimizing avatar quality (quick): Q%d -> %s', quality, naturalsize(size))

            if size > max_size:
                high = quality - bs_step
            else:
                low = quality + bs_step
                best_quality = quality
                best_buffer = buffer.getvalue()
                break
        else:
            raise_for().avatar_too_big()

        # fine-tune with binary search
        while low <= high:
            # round down to the nearest bs_step
            quality = ((low + high) // 2) // bs_step * bs_step

            buffer.seek(0)
            buffer.truncate()

            img.save(buffer, format='WEBP', quality=quality)
            size = buffer.tell()
            logging.debug('Optimizing avatar quality (fine): Q%d -> %s', quality, naturalsize(size))

            if size > max_size:
                high = quality - bs_step
            else:
                low = quality + bs_step
                best_quality = quality
                best_buffer = buffer.getvalue()

        return best_quality, best_buffer


class Avatar:
    @staticmethod
    def get_url(avatar_type: AvatarType, avatar_id: str | int) -> str:
        """
        Get the url of the avatar image.

        >>> Avatar.get_url(AvatarType.custom, '123456')
        '/api/web/avatar/custom/123456'
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

        # optimize file size
        quality, buffer = _optimize_quality(img)
        logging.debug('Optimized avatar quality: Q%d', quality)

        return buffer
