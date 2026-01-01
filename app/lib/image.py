import logging
import warnings
from asyncio import Lock, to_thread
from contextlib import asynccontextmanager
from functools import partial
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NamedTuple, overload

import cython
from blurhash_rs import blurhash_encode
from PIL import ImageOps, ImageSequence
from PIL.Image import Image as PILImage
from PIL.Image import Resampling
from PIL.Image import open as open_image
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
    IMAGE_MAX_FRAMES,
    IMAGE_PROXY_BLURHASH_MAX_COMPONENTS,
    IMAGE_PROXY_IMAGE_MAX_SIDE,
    IMAGE_PROXY_RECOMPRESS_QUALITY,
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


class _Animation(NamedTuple):
    frames: list[PILImage]
    durations: list[int]
    loop: int


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
    async def normalize_proxy_image(data: bytes) -> tuple[bytes, PILImage]:
        return await _normalize_image(
            data,
            quality=IMAGE_PROXY_RECOMPRESS_QUALITY,
            max_side=IMAGE_PROXY_IMAGE_MAX_SIDE,
            return_img=True,
        )

    @staticmethod
    async def create_proxy_thumbnail(
        img: PILImage,
        *,
        max_comp: cython.size_t = IMAGE_PROXY_BLURHASH_MAX_COMPONENTS,
    ) -> str:
        """Generate a BlurHash string from an image."""
        w: cython.size_t
        h: cython.size_t
        w, h = img.size

        # Proportional components
        x_comp: cython.size_t
        y_comp: cython.size_t
        if w >= h:
            x_comp = max_comp
            y_comp = max(1, max_comp * h // w)
        else:
            x_comp = max(1, max_comp * w // h)
            y_comp = max_comp

        # Downscale to 100px
        ratio: cython.double = max(h, w) / 100
        if ratio > 1:
            img = img.resize(
                (
                    max(1, int(w / ratio)),
                    max(1, int(h / ratio)),
                ),
                Resampling.NEAREST,
            )

        return blurhash_encode(img, x_comp, y_comp)


@asynccontextmanager
async def _get_pipeline():
    global _PIPE
    if _PIPE is None:
        pipe_dir = AI_MODELS_DIR.joinpath('Freepik/nsfw_image_detector')
        if not pipe_dir.is_dir():
            warnings.warn(
                'Skipping NSFW image detection: model not found (hint: `ai-models-download`)',
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
    quality: int | None = None,
    min_ratio: float | None = None,
    max_ratio: float | None = None,
    max_megapixels: int | None = None,
    max_side: int | None = None,
    max_file_size: int | None = None,
    return_img: Literal[False] = False,
) -> bytes: ...
@overload
async def _normalize_image(
    data: bytes,
    *,
    quality: int | None = None,
    min_ratio: float | None = None,
    max_ratio: float | None = None,
    max_megapixels: int | None = None,
    max_side: int | None = None,
    max_file_size: int | None = None,
    return_img: Literal[True] = ...,
) -> tuple[bytes, PILImage]: ...
async def _normalize_image(
    data: bytes,
    *,
    quality: int | None = None,
    min_ratio: float | None = None,
    max_ratio: float | None = None,
    max_megapixels: int | None = None,
    max_side: int | None = None,
    max_file_size: int | None = None,
    return_img: bool = False,
) -> bytes | tuple[bytes, PILImage]:
    """
    Normalize the avatar image.

    - Orientation: rotate
    - Shape ratio: crop
    - Megapixels: downscale
    - File size: reduce quality
    """
    img = open_image(BytesIO(data))
    ImageOps.exif_transpose(img, in_place=True)

    # normalize shape ratio
    img_width: cython.size_t
    img_height: cython.size_t
    img_width, img_height = img.size

    crop_box: tuple[int, int, int, int] | None = None
    resize_to: tuple[int, int] | None = None

    # the image is too wide
    if max_ratio is not None and (img_width / img_height) > max_ratio:
        logging.debug('Image is too wide (%dx%d)', img_width, img_height)
        new_width: cython.size_t = int(img_height * max_ratio)
        x1 = (img_width - new_width) // 2
        x2 = (img_width + new_width) // 2
        crop_box = (x1, 0, x2, img_height)
        img_width = new_width

    # the image is too tall
    elif min_ratio is not None and (img_width / img_height) < min_ratio:
        logging.debug('Image is too tall (%dx%d)', img_width, img_height)
        new_height: cython.size_t = int(img_width / min_ratio)
        y1 = (img_height - new_height) // 2
        y2 = (img_height + new_height) // 2
        crop_box = (0, y1, img_width, y2)
        img_height = new_height

    # limit dimensions
    if max_side is not None:
        side_ratio: cython.double = max(img_width, img_height) / max_side
        if side_ratio > 1:
            logging.debug('Image is too big (%dx%d)', img_width, img_height)
            img_width = max(1, int(img_width / side_ratio))
            img_height = max(1, int(img_height / side_ratio))
            resize_to = (img_width, img_height)

    # limit megapixels
    if max_megapixels is not None:
        mp_ratio: cython.double = (img_width * img_height) / max_megapixels
        if mp_ratio > 1:
            logging.debug('Image is too big (%dx%d)', img_width, img_height)
            mp_ratio = sqrt(mp_ratio)
            img_width = max(1, int(img_width / mp_ratio))
            img_height = max(1, int(img_height / mp_ratio))
            resize_to = (img_width, img_height)

    animation = _extract_animation(img)

    if resize_to is None and crop_box is None:
        pass
    elif animation is not None:
        frames: list[PILImage] = []

        for frame in animation.frames:
            if resize_to is not None:
                frame = frame.resize(resize_to, Resampling.BOX, crop_box)
            elif crop_box is not None:
                frame = frame.crop(crop_box)
            frames.append(frame)

        img = frames[0]
        animation = animation._replace(frames=frames)
    elif resize_to is not None:
        img = img.resize(resize_to, Resampling.BOX, crop_box)
    elif crop_box is not None:
        img = img.crop(crop_box)

    async with _get_pipeline() as pipe:
        if pipe is not None:
            preds = await to_thread(partial(pipe, img, top_k=1))
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
        img,
        animation,
        input_size=len(data),
        quality=quality,
        max_file_size=max_file_size,
    )
    logging.debug('Optimized image quality: Q%d', quality)
    return (buffer, img) if return_img else buffer


async def _optimize_quality(
    img: PILImage,
    animation: _Animation | None,
    *,
    input_size: int,
    quality: int | None,
    max_file_size: int | None,
) -> tuple[int, bytes]:
    """
    Find the best image quality given the maximum file size.
    Returns the quality and the image buffer.
    """
    if quality is not None:
        img_bytes = await to_thread(_save, img, quality, animation)
        if len(img_bytes) <= input_size:
            return quality, img_bytes

        img_bytes_lossless = await to_thread(_save, img, -1, animation)
        if len(img_bytes_lossless) <= len(img_bytes):
            return -1, img_bytes_lossless

        return quality, img_bytes

    img_bytes = await to_thread(_save, img, -1, animation)
    img_size = len(img_bytes)
    logging.debug('Optimizing avatar quality (lossless): %s', sizestr(img_size))

    if max_file_size is None or img_size <= max_file_size:
        return -1, img_bytes

    low, high, step = 20, 90, 5

    # initial quick scan
    for quality in range(80, 20 - 1, -20):
        img_bytes = await to_thread(_save, img, quality, animation)
        img_size = len(img_bytes)
        logging.debug(
            'Optimizing avatar quality (quick): Q%d -> %s', quality, sizestr(img_size)
        )

        if img_size > max_file_size:
            high = quality - step
        else:
            low = quality + step
            best_quality = quality
            best_img = img_bytes
            break
    else:
        raise_for.image_too_big()

    # fine-tune with binary search
    while low <= high:
        # round down to the nearest step
        quality = ((low + high) // 2) // step * step

        img_bytes = await to_thread(_save, img, quality, animation)
        img_size = len(img_bytes)
        logging.debug(
            'Optimizing avatar quality (fine): Q%d -> %s', quality, sizestr(img_size)
        )

        if img_size > max_file_size:
            high = quality - step
        else:
            low = quality + step
            best_quality = quality
            best_img = img_bytes

    return best_quality, best_img


def _save(
    img: PILImage,
    quality: int,
    animation: _Animation | None = None,
    *,
    method: int = 0,
) -> bytes:
    buffer = BytesIO()

    if quality < 0:
        quality = -quality if quality < -1 else 80
        lossless = True
    else:
        lossless = False

    # See docs:
    # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#webp
    save_kwargs = {
        'format': 'WebP',
        'lossless': lossless,
        'quality': quality,
        'alpha_quality': min(quality, 75),
        'method': method or (4 if animation is None else 3),
        'exif': b'',
        'xmp': b'',
    }

    if animation is not None:
        animation.frames[0].save(
            buffer,
            **save_kwargs,
            append_images=animation.frames[1:],
            duration=animation.durations,
            loop=animation.loop,
            minimize_size=True,
        )
    else:
        img.save(buffer, **save_kwargs)

    return buffer.getvalue()


@cython.cfunc
def _extract_animation(
    img: PILImage,
    *,
    IMAGE_MAX_FRAMES: cython.size_t = IMAGE_MAX_FRAMES,
):
    n_frames: cython.size_t = getattr(img, 'n_frames', 1)
    if n_frames <= 1:
        return None

    limit: cython.size_t = min(n_frames, IMAGE_MAX_FRAMES)
    frames: list[PILImage] = []
    durations: list[int] = []
    default_duration = int(img.info.get('duration') or 100)
    loop = int(img.info.get('loop') or 0)

    index: cython.size_t
    for index, frame in enumerate(ImageSequence.Iterator(img)):
        bucket = min((index * limit) // n_frames, limit - 1)
        duration = max(int(frame.info.get('duration') or default_duration), 1)

        if bucket == len(frames):
            frames.append(frame.convert('RGBA'))
            durations.append(duration)
        else:
            durations[bucket] += duration

    return _Animation(frames, durations, loop)
