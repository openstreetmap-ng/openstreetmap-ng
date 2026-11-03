from contextlib import asynccontextmanager
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from PIL import GifImagePlugin
from PIL import Image as PILImage
from starlette.exceptions import HTTPException

from app.lib.io import image as image_module
from app.lib.text import translation as translation_module


def _png(width=8, height=8):
    buffer = BytesIO()
    PILImage.new('RGB', (width, height), 'blue').save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def translation(monkeypatch):
    monkeypatch.setattr(translation_module, 't', lambda key: key)


@pytest.fixture
def no_pipeline(monkeypatch):
    @asynccontextmanager
    async def pipeline():
        yield None

    monkeypatch.setattr(image_module, '_get_pipeline', pipeline)


def _message(exc):
    assert exc.status_code == 400
    entry = exc.detail[0]
    assert entry['type'] == 'error' and entry['loc'] == (None, None)
    return entry['msg']


async def test_unidentified_image_has_friendly_feedback(translation):
    with pytest.raises(HTTPException) as exc:
        await image_module.Image.normalize_avatar(b'not an image')
    assert _message(exc.value) == 'validation.image_not_readable'


async def test_truncated_pixel_data_has_friendly_feedback(translation):
    data = _png(64, 64)
    # Preserve a real header, then cut the compressed pixel stream mid-chunk.
    with pytest.raises(HTTPException) as exc:
        await image_module.Image.normalize_avatar(data[:50])
    assert _message(exc.value) == 'validation.image_not_readable'


async def test_real_pillow_pixel_guard_has_friendly_feedback(monkeypatch, translation):
    data = _png(8, 8)
    # Trigger the real Pillow guard with a tiny fixture, without a huge allocation.
    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 20)
    with pytest.raises(HTTPException) as exc:
        await image_module.Image.normalize_avatar(data)
    assert _message(exc.value) == 'validation.image_dimensions_too_big'


async def test_pillow_soft_warning_is_still_accepted(monkeypatch, no_pipeline):
    data = _png(8, 8)
    monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 40)
    with pytest.warns(PILImage.DecompressionBombWarning):
        normalized = await image_module.Image.normalize_avatar(data)
    assert PILImage.open(BytesIO(normalized)).size == (8, 8)


async def test_valid_photo_is_still_downscaled(no_pipeline):
    normalized = await image_module.Image.normalize_avatar(_png(800, 600))
    result = PILImage.open(BytesIO(normalized))
    assert result.width * result.height <= 384 * 384


@pytest.mark.parametrize('stage', ['exif', 'animation'])
async def test_lazy_decode_errors_have_friendly_feedback(
    monkeypatch, translation, stage
):
    def fail(*args, **kwargs):
        raise OSError('synthetic lazy decoder failure')

    data = _png()
    animation_frames = []
    if stage == 'exif':
        monkeypatch.setattr(image_module.ImageOps, 'exif_transpose', fail)
    else:
        buffer = BytesIO()
        PILImage.new('RGB', (8, 8), 'blue').save(
            buffer,
            format='GIF',
            save_all=True,
            append_images=[PILImage.new('RGB', (8, 8), 'red')],
            duration=100,
            loop=0,
        )
        data = buffer.getvalue()
        seek = GifImagePlugin.GifImageFile.seek

        def fail_animation(image, frame):
            if frame == 1:
                animation_frames.append(frame)
                fail()
            return seek(image, frame)

        monkeypatch.setattr(GifImagePlugin.GifImageFile, 'seek', fail_animation)
    with pytest.raises(HTTPException) as exc:
        await image_module.Image.normalize_avatar(data)
    assert _message(exc.value) == 'validation.image_not_readable'
    if stage == 'animation':
        assert animation_frames == [1]


async def test_output_encoder_error_is_not_mislabeled_as_input(
    monkeypatch, no_pipeline
):
    monkeypatch.setattr(
        image_module,
        '_optimize_quality',
        AsyncMock(side_effect=OSError('encoder failure')),
    )
    with pytest.raises(OSError, match='encoder failure'):
        await image_module.Image.normalize_avatar(_png())


async def test_pipeline_error_is_not_mislabeled_as_input(monkeypatch):
    @asynccontextmanager
    async def fail():
        raise OSError('model failure')
        yield None

    monkeypatch.setattr(image_module, '_get_pipeline', fail)
    with pytest.raises(OSError, match='model failure'):
        await image_module.Image.normalize_avatar(_png())
