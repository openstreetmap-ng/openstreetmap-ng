from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image as PILImage

from app.config import IMAGE_MAX_FRAMES
from app.exceptions.api_error import APIError
from app.exceptions.context import exceptions_context
from app.exceptions.default import Exceptions
from app.lib.io import image as image_module
from app.lib.io.image import Image


@pytest.mark.parametrize(
    'normalize', [Image.normalize_avatar, Image.normalize_background]
)
@pytest.mark.parametrize('side', [10_000, 20_000])
async def test_normalize_oversized_image(normalize, side):
    # PPM headers exercise Pillow's real warning/error thresholds without
    # allocating a decompressed image or changing its global pixel limit.
    data = f'P6\n{side} {side}\n255\n'.encode()
    with exceptions_context(Exceptions()), pytest.raises(APIError) as exc:
        await normalize(data)
    assert exc.value.status_code == 413
    assert exc.value.detail == 'Image is too large'


@pytest.mark.parametrize(
    'normalize', [Image.normalize_avatar, Image.normalize_background]
)
@pytest.mark.parametrize('data', [b'not an image', b'P6\n2 2\n255\n\x00'])
async def test_normalize_unreadable_image(normalize, data):
    # Include data with a valid header that fails only when pixels are loaded.
    with exceptions_context(Exceptions()), pytest.raises(APIError) as exc:
        await normalize(data)
    assert exc.value.status_code == 422
    assert exc.value.detail == 'Image could not be read. Please upload a valid image.'


async def test_normalize_valid_image_after_rejection(monkeypatch):
    @asynccontextmanager
    async def no_classifier():
        yield None

    monkeypatch.setattr(image_module, '_get_pipeline', no_classifier)
    data = BytesIO()
    PILImage.new('RGB', (4, 4), 'red').save(data, format='PNG')
    with exceptions_context(Exceptions()):
        with pytest.raises(APIError):
            await Image.normalize_avatar(b'not an image')
        normalized = await Image.normalize_avatar(data.getvalue())
    with PILImage.open(BytesIO(normalized)) as result:
        assert result.size == (4, 4)
        assert result.format == 'WEBP'


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
