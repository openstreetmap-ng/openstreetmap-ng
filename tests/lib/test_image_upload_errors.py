import warnings
from io import BytesIO

import pytest
from PIL import Image as PILImage

from app.exceptions.api_error import APIError
from app.exceptions.context import exceptions_context
from app.exceptions.default import Exceptions
from app.lib.io.image import Image, _image_decode_errors


def _png(size=(8, 8)):
    buffer = BytesIO()
    PILImage.new('RGB', size, 'green').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.mark.parametrize('data', [b'', b'not an image', b'\x89PNG\r\n\x1a\n'])
async def test_unreadable_image_has_friendly_error(data):
    with exceptions_context(Exceptions()), pytest.raises(APIError) as error:
        await Image.normalize_avatar(data)
    assert error.value.status_code == 422
    assert 'image' in error.value.detail.lower()


async def test_decompression_bomb_has_friendly_size_error(monkeypatch):
    data = _png()
    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 10)
    with exceptions_context(Exceptions()), pytest.raises(APIError) as error:
        await Image.normalize_avatar(data)
    assert error.value.status_code == 413


async def test_decompression_warning_as_error_has_friendly_size_error(monkeypatch):
    data = _png((4, 4))
    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 10)
    with warnings.catch_warnings():
        warnings.simplefilter('error', PILImage.DecompressionBombWarning)
        with exceptions_context(Exceptions()), pytest.raises(APIError) as error:
            await Image.normalize_avatar(data)
    assert error.value.status_code == 413


async def test_valid_small_image_still_normalizes():
    with exceptions_context(Exceptions()):
        result = await Image.normalize_avatar(_png())
    with PILImage.open(BytesIO(result)) as image:
        assert image.format == 'WEBP'
        assert image.size == (8, 8)


async def test_background_decode_uses_the_same_friendly_error():
    with exceptions_context(Exceptions()), pytest.raises(APIError) as error:
        await Image.normalize_background(b'not an image')
    assert error.value.status_code == 422


def test_decode_error_boundary_does_not_hide_programming_errors():
    with (
        pytest.raises(RuntimeError, match='not an input failure'),
        _image_decode_errors(),
    ):
        raise RuntimeError('not an input failure')


@pytest.mark.parametrize(
    ('exception', 'status'),
    [
        (PILImage.DecompressionBombError, 413),
        (PILImage.DecompressionBombWarning, 413),
        (OSError, 422),
        (SyntaxError, 422),
    ],
)
def test_all_decode_exception_types_are_mapped(exception, status):
    with (
        exceptions_context(Exceptions()),
        pytest.raises(APIError) as error,
        _image_decode_errors(),
    ):
        raise exception('invalid image data')
    assert error.value.status_code == status
