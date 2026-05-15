from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image as PILImage

from app.config import IMAGE_MAX_FRAMES
from app.exceptions import Exceptions
from app.exceptions.api_error import APIError
from app.lib.exceptions_context import exceptions_context
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


async def test_normalize_avatar_rejects_decompression_bomb(monkeypatch):
    image = PILImage.new('RGB', (2, 2))
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    monkeypatch.setattr('PIL.Image.MAX_IMAGE_PIXELS', 1)

    with exceptions_context(Exceptions()), pytest.raises(APIError) as exc_info:
        await Image.normalize_avatar(buffer.getvalue())

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == 'Image is too large'


async def test_normalize_avatar_rejects_invalid_image():
    with exceptions_context(Exceptions()), pytest.raises(APIError) as exc_info:
        await Image.normalize_avatar(b'not an image')

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == 'Image is invalid'
