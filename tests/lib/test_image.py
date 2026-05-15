from io import BytesIO
from pathlib import Path

import pytest
from starlette import status
from PIL import Image as PILImage

from app.exceptions.api_error import APIError
from app.config import IMAGE_MAX_FRAMES
from app.lib.image import Image


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


async def test_normalize_avatar_rejects_invalid_image():
    with pytest.raises(APIError) as exc_info:
        await Image.normalize_avatar(b'not an image')

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert exc_info.value.detail == 'Image file is invalid or unsupported'


async def test_normalize_avatar_rejects_decompression_bomb(monkeypatch):
    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 1)
    buffer = BytesIO()
    PILImage.new('RGB', (3, 1)).save(buffer, format='PNG')

    with pytest.raises(APIError) as exc_info:
        await Image.normalize_avatar(buffer.getvalue())

    assert exc_info.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert exc_info.value.detail == 'Image is too large'
