from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image as PILImage
from PIL.Image import DecompressionBombError

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


async def test_normalize_avatar_unreadable_bytes():
    with exceptions_context(Exceptions()), pytest.raises(APIError) as exc_info:
        await Image.normalize_avatar(b'invalid_corrupt_non_image_payload')
    assert exc_info.value.status_code == 422
    assert 'not readable' in exc_info.value.detail.lower()


async def test_normalize_avatar_decompression_bomb():
    with (
        exceptions_context(Exceptions()),
        patch(
            'app.lib.io.image.open_image', side_effect=DecompressionBombError('Bomb')
        ),
        pytest.raises(APIError) as exc_info,
    ):
        await Image.normalize_avatar(b'fake_bomb_bytes')
    assert exc_info.value.status_code == 413
    assert 'too large' in exc_info.value.detail.lower()
