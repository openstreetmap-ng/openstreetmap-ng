from io import BytesIO
from pathlib import Path

import pytest
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


@pytest.mark.parametrize('pixel_limit', [400, 600])
async def test_avatar_decompression_limit_is_friendly(monkeypatch, pixel_limit):
    buffer = BytesIO()
    PILImage.new('RGB', (32, 32)).save(buffer, format='PNG')
    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', pixel_limit)
    with pytest.raises(APIError) as error:
        await Image.normalize_avatar(buffer.getvalue())
    assert error.value.status_code == 413
    assert error.value.detail == 'Image is too large'


@pytest.mark.parametrize('truncated', [False, True])
async def test_unreadable_avatar_is_friendly(truncated):
    if truncated:
        buffer = BytesIO()
        PILImage.new('RGB', (16, 16)).save(buffer, format='BMP')
        data = buffer.getvalue()[:-100]
    else:
        data = b'not an image'
    with pytest.raises(APIError) as error:
        await Image.normalize_avatar(data)
    assert error.value.status_code == 422
    assert (
        error.value.detail
        == 'Image could not be read. Please choose a different image.'
    )


async def test_small_valid_avatar_still_normalizes():
    buffer = BytesIO()
    PILImage.new('RGB', (16, 16), 'red').save(buffer, format='PNG')
    normalized = await Image.normalize_avatar(buffer.getvalue())
    with PILImage.open(BytesIO(normalized)) as result:
        assert result.format == 'WEBP'
        assert result.size == (16, 16)
