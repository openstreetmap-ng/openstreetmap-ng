from contextlib import asynccontextmanager
from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image as PILImage

from app.lib.io import image as image_module
from app.lib.text import translation as translation_module


class ImageFeedbackError(Exception):
    pass


@pytest.fixture
def feedback(monkeypatch):
    error = Mock(side_effect=ImageFeedbackError)
    monkeypatch.setattr(image_module.StandardFeedback, 'raise_error', error)
    monkeypatch.setattr(translation_module, 't', lambda key: key)
    return error


def png(size=(2, 2)):
    buffer = BytesIO()
    PILImage.new('RGB', size, 'red').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.mark.parametrize('kind', ['avatar', 'background', 'proxy_image'])
async def test_unreadable_upload_has_friendly_feedback(kind, feedback):
    with pytest.raises(ImageFeedbackError):
        await getattr(image_module.Image, f'normalize_{kind}')(b'not an image')
    assert feedback.call_args.args == (None, 'validation.image_not_readable')


@pytest.mark.parametrize('size', [(2, 2), (3, 3)])
async def test_pillow_pixel_warning_and_error_are_friendly(size, monkeypatch, feedback):
    data = png(size)
    # Exercise Pillow's real limit checks with tiny images, without large allocations.
    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 2)
    with pytest.raises(ImageFeedbackError):
        await image_module.Image.normalize_avatar(data)
    assert feedback.call_args.args == (None, 'validation.image_dimensions_too_big')


@pytest.mark.parametrize(
    'error', [OSError('truncated'), SyntaxError('bad data'), EOFError()]
)
async def test_lazy_decode_errors_are_friendly(error, monkeypatch, feedback):
    monkeypatch.setattr(
        image_module.ImageOps, 'exif_transpose', Mock(side_effect=error)
    )
    with pytest.raises(ImageFeedbackError):
        await image_module.Image.normalize_avatar(png())
    assert feedback.call_args.args == (None, 'validation.image_not_readable')
    assert feedback.call_args.kwargs['exc'] is error


async def test_later_animation_frame_error_is_friendly(monkeypatch, feedback):
    buffer = BytesIO()
    PILImage.new('RGB', (2, 2), 'red').save(
        buffer,
        format='GIF',
        save_all=True,
        append_images=[PILImage.new('RGB', (2, 2), 'blue')],
    )
    monkeypatch.setattr(
        image_module.ImageSequence, 'Iterator', Mock(side_effect=OSError('frame'))
    )
    with pytest.raises(ImageFeedbackError):
        await image_module.Image.normalize_avatar(buffer.getvalue())
    assert feedback.call_args.args == (None, 'validation.image_not_readable')


async def test_programming_errors_are_not_misreported(monkeypatch, feedback):
    monkeypatch.setattr(
        image_module.ImageOps, 'exif_transpose', Mock(side_effect=RuntimeError('bug'))
    )
    with pytest.raises(RuntimeError, match='bug'):
        await image_module.Image.normalize_avatar(png())
    feedback.assert_not_called()


async def test_small_valid_image_still_normalizes(monkeypatch, feedback):
    @asynccontextmanager
    async def no_model():
        yield None

    monkeypatch.setattr(image_module, '_get_pipeline', no_model)
    result = await image_module.Image.normalize_avatar(png())
    with PILImage.open(BytesIO(result)) as image:
        assert image.size == (2, 2)
        assert image.format == 'WEBP'
    feedback.assert_not_called()
