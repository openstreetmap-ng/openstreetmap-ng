import logging
import warnings
from asyncio import Lock, get_running_loop
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

import blurhash
import cv2
import cython
import numpy as np
from cv2.typing import MatLike
from numpy.typing import NDArray
from PIL import Image as PILImage
from sizestr import sizestr

from app.config import (
    AI_MODELS_DIR,
    AI_TRANSFORMERS_DEVICE,
    AVATAR_MAX_FILE_SIZE,
    AVATAR_MAX_MEGAPIXELS,
    AVATAR_MAX_RATIO,
    BACKGROUND_MAX_FILE_SIZE,
    BACKGROUND_MAX_MEGAPIXELS,
    BACKGROUND_MAX_RATIO,
    IMAGE_PROXY_BLURHASH_MAX_COMPONENTS,
)
from app.lib.exceptions_context import raise_for
from app.models.types import NoteId, StorageKey, UserId

if TYPE_CHECKING:
    from transformers import ImageClassificationPipeline

if cython.compiled:
    from cython.cimports.libc.math import sqrt
else:
    from math import sqrt

# TODO: test 200MP file

UserAvatarType = Literal['gravatar', 'custom'] | None
AvatarType = Literal['anonymous_note', 'initials'] | UserAvatarType

DEFAULT_USER_AVATAR_URL = '/static/img/avatar.webp'
DEFAULT_USER_AVATAR = Path('app' + DEFAULT_USER_AVATAR_URL).read_bytes()
DEFAULT_APP_AVATAR_URL = '/static/img/app.webp'

_PIPE: 'ImageClassificationPipeline | None' = None
_PIPE_LOCK = Lock()


class Image:
    @staticmethod
    @overload
    def get_avatar_url(
        image_type: None,
        *,
        app: bool = False,
    ) -> str: ...
    @staticmethod
    @overload
    def get_avatar_url(
        image_type: Literal['anonymous_note'],
        image_id: NoteId,
    ) -> str: ...
    @staticmethod
    @overload
    def get_avatar_url(
        image_type: Literal['initials', 'gravatar'],
        image_id: UserId,
    ) -> str: ...
    @staticmethod
    @overload
    def get_avatar_url(
        image_type: Literal['custom'],
        image_id: StorageKey,
    ) -> str: ...
    @staticmethod
    def get_avatar_url(
        image_type: AvatarType,
        image_id: UserId | NoteId | StorageKey | None = None,
        *,
        app: bool = False,
    ) -> str:
        """Get the url of the avatar image."""
        return (
            f'/api/web/img/avatar/{image_type}/{image_id}'
            if image_type is not None
            else (DEFAULT_APP_AVATAR_URL if app else DEFAULT_USER_AVATAR_URL)
        )

    @staticmethod
    async def normalize_avatar(data: bytes) -> bytes:
        """Normalize the avatar image."""
        return await _normalize_image(
            data,
            min_ratio=1 / AVATAR_MAX_RATIO,
            max_ratio=AVATAR_MAX_RATIO,
            max_megapixels=AVATAR_MAX_MEGAPIXELS,
            max_file_size=AVATAR_MAX_FILE_SIZE,
        )

    @staticmethod
    def get_background_url(image_id: StorageKey | None) -> str | None:
        """Get the url of the background image."""
        return (
            f'/api/web/img/background/custom/{image_id}'
            if image_id is not None
            else None
        )

    @staticmethod
    async def normalize_background(data: bytes) -> bytes:
        """Normalize the background image."""
        return await _normalize_image(
            data,
            min_ratio=1 / BACKGROUND_MAX_RATIO,
            max_ratio=BACKGROUND_MAX_RATIO,
            max_megapixels=BACKGROUND_MAX_MEGAPIXELS,
            max_file_size=BACKGROUND_MAX_FILE_SIZE,
        )

    @staticmethod
    async def normalize_proxy_image(
        data: bytes,
        *,
        max_side: int,
        quality: int,
    ) -> tuple[bytes, MatLike]:
        return await _normalize_image(
            data,
            quality=quality,
            max_side=max_side,
            return_mat=True,
        )

    @staticmethod
    async def create_proxy_thumbnail(
        img: MatLike,
        *,
        max_comp: cython.uint = IMAGE_PROXY_BLURHASH_MAX_COMPONENTS,
    ) -> str:
        """Generate a BlurHash string from an image."""
        h: cython.uint = img.shape[0]
        w: cython.uint = img.shape[1]

        # Proportional components
        x_comp: cython.uint
        y_comp: cython.uint
        if w >= h:
            x_comp = max_comp
            y_comp = max(1, int(max_comp * h / w))
        else:
            x_comp = max(1, int(max_comp * w / h))
            y_comp = max_comp

        # Downscale to 100px
        ratio: cython.double = max(h, w) / 100
        if ratio > 1:
            img = cv2.resize(
                img,
                (
                    max(1, int(w / ratio)),
                    max(1, int(h / ratio)),
                ),
                interpolation=cv2.INTER_AREA,
            )

        # Encode to BlurHash
        with PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)) as pil_img:
            loop = get_running_loop()
            return await loop.run_in_executor(
                None,
                blurhash.encode,
                pil_img,
                x_comp,
                y_comp,
            )


@asynccontextmanager
async def _get_pipeline():
    global _PIPE
    if _PIPE is None:
        pipe_dir = AI_MODELS_DIR.joinpath('Freepik/nsfw_image_detector')
        if not pipe_dir.is_dir():
            warnings.warn(
                'Skipping NSFW image detection: model not found (hint run: ai-models-download)',
                stacklevel=1,
            )
            yield None
            return

        # Lazy import for faster startup
        from transformers import pipeline  # noqa: PLC0415

        _PIPE = pipeline(  # pyright: ignore[reportConstantRedefinition]
            'image-classification',
            model=str(pipe_dir),
            device=AI_TRANSFORMERS_DEVICE,
        )
    async with _PIPE_LOCK:
        yield _PIPE


@overload
async def _normalize_image(
    data: bytes,
    *,
    quality: cython.int = 0,
    min_ratio: cython.double = 0,
    max_ratio: cython.double = 0,
    max_megapixels: cython.uint = 0,
    max_side: cython.uint = 0,
    max_file_size: cython.uint = 0,
    return_mat: Literal[False] = False,
) -> bytes: ...
@overload
async def _normalize_image(
    data: bytes,
    *,
    quality: cython.int = 0,
    min_ratio: cython.double = 0,
    max_ratio: cython.double = 0,
    max_megapixels: cython.uint = 0,
    max_side: cython.uint = 0,
    max_file_size: cython.uint = 0,
    return_mat: Literal[True] = ...,
) -> tuple[bytes, MatLike]: ...
async def _normalize_image(
    data: bytes,
    *,
    quality: cython.int = 0,
    min_ratio: cython.double = 0,
    max_ratio: cython.double = 0,
    max_megapixels: cython.uint = 0,
    max_side: cython.uint = 0,
    max_file_size: cython.uint = 0,
    return_mat: bool = False,
) -> bytes | tuple[bytes, MatLike]:
    """
    Normalize the avatar image.

    - Orientation: rotate
    - Shape ratio: crop
    - Megapixels: downscale
    - File size: reduce quality
    """
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

    # normalize shape ratio
    img_height: cython.uint = img.shape[0]
    img_width: cython.uint = img.shape[1]
    ratio: cython.double = img_width / img_height

    # the image is too wide
    if max_ratio and ratio > max_ratio:
        logging.debug('Image is too wide %dx%d', img_width, img_height)
        new_width: cython.uint = int(img_height * max_ratio)
        x1: cython.uint = (img_width - new_width) // 2
        x2: cython.uint = (img_width + new_width) // 2
        img = img[:, x1:x2]
        img_width = x2 - x1

    # the image is too tall
    elif min_ratio and ratio < min_ratio:
        logging.debug('Image is too tall %dx%d', img_width, img_height)
        new_height: cython.uint = int(img_width / min_ratio)
        y1: cython.uint = (img_height - new_height) // 2
        y2: cython.uint = (img_height + new_height) // 2
        img = img[y1:y2, :]
        img_height = y2 - y1

    # normalize megapixels
    if max_megapixels:
        mp_ratio: cython.double = (img_width * img_height) / max_megapixels
        if mp_ratio > 1:
            logging.debug('Image is too big %dx%d', img_width, img_height)
            mp_ratio = sqrt(mp_ratio)
            img_width = max(1, int(img_width / mp_ratio))
            img_height = max(1, int(img_height / mp_ratio))
            img = cv2.resize(img, (img_width, img_height), interpolation=cv2.INTER_AREA)

    if max_side:
        side_ratio: cython.double = max(img_width, img_height) / max_side
        if side_ratio > 1:
            img_width = max(1, int(img_width / side_ratio))
            img_height = max(1, int(img_height / side_ratio))
            img = cv2.resize(img, (img_width, img_height), interpolation=cv2.INTER_AREA)

    async with _get_pipeline() as pipe:
        if pipe is not None:
            with PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)) as img_pil:
                loop = get_running_loop()
                preds = await loop.run_in_executor(
                    None, partial(pipe, img_pil, top_k=1)
                )
                # Example preds: [{'label': 'neutral', 'score': 0.92}, ...]

            top = preds[0]
            label: Literal['neutral', 'low', 'medium', 'high'] = top['label']
            score: float = top['score']
            logging.debug('NSFW image scan: %s=%.3f', label, score)
            if label in {'medium', 'high'}:
                from app.services.audit_service import audit  # noqa: PLC0415

                await audit('nsfw_image', extra=top)
                raise_for.image_inappropriate()

    # optimize file size
    quality, buffer = await _optimize_quality(
        img, quality=quality, max_file_size=max_file_size
    )
    logging.debug('Optimized image quality: Q%d', quality)
    return (buffer, img) if return_mat else buffer


async def _optimize_quality(
    img: MatLike,
    *,
    quality: cython.int,
    max_file_size: cython.uint,
) -> tuple[int, bytes]:
    """
    Find the best image quality given the maximum file size.
    Returns the quality and the image buffer.
    """
    loop = get_running_loop()

    if quality:
        _, img_ = await loop.run_in_executor(
            None, cv2.imencode, '.webp', img, (cv2.IMWRITE_WEBP_QUALITY, quality)
        )
        return quality, img_.tobytes()

    _, img_ = await loop.run_in_executor(
        None, cv2.imencode, '.webp', img, (cv2.IMWRITE_WEBP_QUALITY, 101)
    )
    size: cython.uint = img_.size
    logging.debug('Optimizing avatar quality (lossless): %s', sizestr(size))

    if not max_file_size or size <= max_file_size:
        return -1, img_.tobytes()

    high: cython.int = 90
    low: cython.int = 20
    bs_step: cython.uint = 5
    best_quality: cython.int = -1
    best_img: NDArray[np.uint8] | None = None

    # initial quick scan
    for quality in range(80, 20 - 1, -20):  # noqa: PLR1704
        _, img_ = await loop.run_in_executor(
            None, cv2.imencode, '.webp', img, (cv2.IMWRITE_WEBP_QUALITY, quality)
        )
        size = img_.size
        logging.debug(
            'Optimizing avatar quality (quick): Q%d -> %s', quality, sizestr(size)
        )

        if size > max_file_size:
            high = quality - bs_step
        else:
            low = quality + bs_step
            best_quality = quality
            best_img = img_
            break
    else:
        raise_for.image_too_big()

    # fine-tune with binary search
    while low <= high:
        # round down to the nearest bs_step
        quality = ((low + high) // 2) // bs_step * bs_step

        _, img_ = await loop.run_in_executor(
            None, cv2.imencode, '.webp', img, (cv2.IMWRITE_WEBP_QUALITY, quality)
        )
        size = img_.size
        logging.debug(
            'Optimizing avatar quality (fine): Q%d -> %s', quality, sizestr(size)
        )

        if size > max_file_size:
            high = quality - bs_step
        else:
            low = quality + bs_step
            best_quality = quality
            best_img = img_

    return best_quality, best_img.tobytes()
