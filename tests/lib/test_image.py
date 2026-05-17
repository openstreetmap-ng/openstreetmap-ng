from io import BytesIO
from math import isqrt
from pathlib import Path
from struct import pack
from zlib import crc32

import pytest
from PIL import Image as PILImage
from starlette import status

from app.config import IMAGE_MAX_FRAMES
from app.exceptions.api_error import APIError
from app.exceptions.context import exceptions_context
from app.exceptions.default import Exceptions
from app.lib.io.image import Image


@pytest.mark.parametrize(
    ('image_type', 'image_id', 'expected'),
    [
        ('gravatar', 123, '/api/web/img/avatar/gravatar/123'),
        ('custom', '123', '/api/web/img/avatar/custom/123'),
    ],
)
def test_get_avatar_url(image_type, image_id, expected):
    assert Image.get_avatar_url(image_type, image_id) == expected


@pytest.mark.parametrize(
    ('app', 'expected'),
    [
        (False, '/static/img/avatar.webp'),
        (True, '/static/img/app.webp'),
    ],
)
def test_default_avatar_url(app, expected):
    assert Image.get_avatar_url(None, app=app) == expected


@pytest.fixture(scope='module')
def animation():
    return Path('tests/data/animation.gif').read_bytes()


@pytest.mark.extended
async def test_normalize_avatar_preserves_animation(animation: bytes):
    normalized = await Image.normalize_proxy_image(animation)
    result = PILImage.open(BytesIO(normalized[0]))
    assert len(normalized[0]) < len(animation)
    assert result.is_animated  # type: ignore
    assert 1 < result.n_frames <= IMAGE_MAX_FRAMES  # type: ignore


def _png_chunk(chunk_type: bytes, data: bytes):
    return (
        pack('>I', len(data))
        + chunk_type
        + data
        + pack('>I', crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _png_header(width: int, height: int):
    return (
        b'\x89PNG\r\n\x1a\n'
        + _png_chunk(b'IHDR', pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b'IEND', b'')
    )


def _decompression_bomb_error_png_header():
    return _png_header(200_000, 200_000)


def _decompression_bomb_warning_png_header():
    max_pixels = PILImage.MAX_IMAGE_PIXELS
    assert max_pixels is not None

    side = isqrt(max_pixels) + 1
    assert max_pixels < side * side < max_pixels * 2
    return _png_header(side, side)


@pytest.mark.parametrize(
    'image_data',
    [
        _decompression_bomb_warning_png_header(),
        _decompression_bomb_error_png_header(),
    ],
)
async def test_normalize_avatar_reports_decompression_bombs_as_too_large(
    image_data: bytes,
):
    with (
        exceptions_context(Exceptions()),
        pytest.raises(APIError) as exc_info,
    ):
        await Image.normalize_avatar(image_data)

    assert exc_info.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE
