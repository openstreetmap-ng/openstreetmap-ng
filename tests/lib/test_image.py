from io import BytesIO
from pathlib import Path

import pytest
from fastapi import status
from PIL import Image as PILImage

from app.config import IMAGE_MAX_FRAMES
from app.exceptions.api_error import APIError
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


async def test_normalize_avatar_handles_decompression_bomb(monkeypatch):
    buffer = BytesIO()
    PILImage.new('RGB', (10, 10), 'white').save(buffer, format='PNG')

    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 1)

    with pytest.raises(APIError) as e:
        await Image.normalize_avatar(buffer.getvalue())

    assert e.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert e.value.detail == 'Image is too large'
