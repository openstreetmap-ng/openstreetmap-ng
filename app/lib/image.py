import logging
from asyncio import get_running_loop
from enum import Enum
from pathlib import Path
from typing import Literal, overload

import cv2
import cython
import numpy as np
from cv2.typing import MatLike
from numpy.typing import NDArray
from sizestr import sizestr

from app.lib.exceptions_context import raise_for
from app.limits import (
    AVATAR_MAX_FILE_SIZE,
    AVATAR_MAX_MEGAPIXELS,
    AVATAR_MAX_RATIO,
    BACKGROUND_MAX_FILE_SIZE,
    BACKGROUND_MAX_MEGAPIXELS,
    BACKGROUND_MAX_RATIO,
)
from app.models.types import StorageKey

if cython.compiled:
    from cython.cimports.libc.math import sqrt
else:
    from math import sqrt

# TODO: test 200MP file


class AvatarType(str, Enum):
    default = 'default'
    gravatar = 'gravatar'
    custom = 'custom'


class Image:
    default_avatar: bytes = Path('app/static/img/avatar.webp').read_bytes()

    @overload
    @staticmethod
    def get_avatar_url(image_type: Literal[AvatarType.default], *, app: bool = False) -> str: ...

    @overload
    @staticmethod
    def get_avatar_url(image_type: Literal[AvatarType.gravatar], image_id: int) -> str: ...

    @overload
    @staticmethod
    def get_avatar_url(image_type: Literal[AvatarType.custom], image_id: StorageKey) -> str: ...

    @staticmethod
    def get_avatar_url(image_type: AvatarType, image_id: int | StorageKey = 0, *, app: bool = False) -> str:
        """
        Get the url of the avatar image.

        >>> Image.get_avatar_url(AvatarType.custom, '123456')
        '/api/web/avatar/123456'
        """
        if image_type == AvatarType.default:
            return '/static/img/avatar.webp' if not app else '/static/img/app.webp'
        elif image_type == AvatarType.gravatar:
            return f'/api/web/gravatar/{image_id}'
        elif image_type == AvatarType.custom:
            return f'/api/web/avatar/{image_id}'
        else:
            raise NotImplementedError(f'Unsupported avatar type {image_type!r}')

    @staticmethod
    async def normalize_avatar(data: bytes) -> bytes:
        """
        Normalize the avatar image.
        """
        return await _normalize_image(
            data,
            min_ratio=1 / AVATAR_MAX_RATIO,
            max_ratio=AVATAR_MAX_RATIO,
            max_megapixels=AVATAR_MAX_MEGAPIXELS,
            max_file_size=AVATAR_MAX_FILE_SIZE,
        )

    @staticmethod
    def get_background_url(image_id: StorageKey | None) -> str | None:
        """
        Get the url of the background image.

        >>> Image.get_background_url('123456')
        '/api/web/background/123456'
        """
        if image_id is not None:
            return f'/api/web/background/{image_id}'
        else:
            return None

    @staticmethod
    async def normalize_background(data: bytes) -> bytes:
        """
        Normalize the background image.
        """
        return await _normalize_image(
            data,
            min_ratio=1 / BACKGROUND_MAX_RATIO,
            max_ratio=BACKGROUND_MAX_RATIO,
            max_megapixels=BACKGROUND_MAX_MEGAPIXELS,
            max_file_size=BACKGROUND_MAX_FILE_SIZE,
        )


async def _normalize_image(
    data: bytes,
    *,
    min_ratio: cython.double,
    max_ratio: cython.double,
    max_megapixels: cython.int,
    max_file_size: cython.int,
) -> bytes:
    """
    Normalize the avatar image.

    - Orientation: rotate
    - Shape ratio: crop
    - Megapixels: downscale
    - File size: reduce quality
    """
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

    # normalize shape ratio
    img_height: cython.int = img.shape[0]
    img_width: cython.int = img.shape[1]
    ratio: cython.double = img_width / img_height

    # image is too wide
    if max_ratio and ratio > max_ratio:
        logging.debug('Image is too wide %dx%d', img_width, img_height)
        new_width: cython.int = int(img_height * max_ratio)
        x1: cython.int = (img_width - new_width) // 2
        x2: cython.int = (img_width + new_width) // 2
        img = img[:, x1:x2]
        img_width = x2 - x1

    # image is too tall
    elif min_ratio and ratio < min_ratio:
        logging.debug('Image is too tall %dx%d', img_width, img_height)
        new_height: cython.int = int(img_width / min_ratio)
        y1: cython.int = (img_height - new_height) // 2
        y2: cython.int = (img_height + new_height) // 2
        img = img[y1:y2, :]
        img_height = y2 - y1

    # normalize megapixels
    if max_megapixels:
        mp_ratio: cython.double = (img_width * img_height) / max_megapixels
        if mp_ratio > 1:
            logging.debug('Image is too big %dx%d', img_width, img_height)
            mp_ratio = sqrt(mp_ratio)
            img_width = int(img_width / mp_ratio)
            img_height = int(img_height / mp_ratio)
            img = cv2.resize(img, (img_width, img_height), interpolation=cv2.INTER_AREA)

    # optimize file size
    quality, buffer = await _optimize_quality(img, max_file_size)
    logging.debug('Optimized avatar quality: Q%d', quality)
    return buffer


async def _optimize_quality(img: MatLike, max_file_size: int | None) -> tuple[int, bytes]:
    """
    Find the best image quality given the maximum file size.

    Returns the quality and the image buffer.
    """
    loop = get_running_loop()

    _, img_ = await loop.run_in_executor(None, cv2.imencode, '.webp', img, (cv2.IMWRITE_WEBP_QUALITY, 101))
    size = img_.size
    logging.debug('Optimizing avatar quality (lossless): %s', sizestr(size))

    if max_file_size is None or size <= max_file_size:
        return -1, img_.tobytes()

    high: cython.int = 90
    low: cython.int = 20
    bs_step: cython.int = 5
    best_quality: cython.int = -1
    best_img: NDArray[np.uint8] | None = None

    # initial quick scan
    quality: cython.int
    for quality in range(80, 20 - 1, -20):
        _, img_ = await loop.run_in_executor(None, cv2.imencode, '.webp', img, (cv2.IMWRITE_WEBP_QUALITY, quality))
        size = img_.size
        logging.debug('Optimizing avatar quality (quick): Q%d -> %s', quality, sizestr(size))

        if size > max_file_size:
            high = quality - bs_step
        else:
            low = quality + bs_step
            best_quality = quality
            best_img = img_
            break
    else:
        raise_for().image_too_big()

    # fine-tune with binary search
    while low <= high:
        # round down to the nearest bs_step
        quality = ((low + high) // 2) // bs_step * bs_step

        _, img_ = await loop.run_in_executor(None, cv2.imencode, '.webp', img, (cv2.IMWRITE_WEBP_QUALITY, quality))
        size = img_.size
        logging.debug('Optimizing avatar quality (fine): Q%d -> %s', quality, sizestr(size))

        if size > max_file_size:
            high = quality - bs_step
        else:
            low = quality + bs_step
            best_quality = quality
            best_img = img_

    return best_quality, best_img.tobytes()
