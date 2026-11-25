from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image as PILImage

from app.config import AVATAR_UPLOAD_MAX_SIZE
from app.exceptions.api06 import Exceptions06
from app.exceptions.api_error import APIError
from app.exceptions.context import exceptions_context
from app.services import image_service
from app.services.image_service import ImageService


@pytest.mark.parametrize('kind', ['bytes', 'pixels', 'invalid', 'truncated'])
async def test_bad_avatar_has_friendly_error_without_storage(monkeypatch, kind):
    save = AsyncMock()
    monkeypatch.setattr(image_service, 'AVATAR_STORAGE', SimpleNamespace(save=save))
    if kind == 'bytes':
        data = bytes(AVATAR_UPLOAD_MAX_SIZE + 1)
    elif kind == 'invalid':
        data = b'This is not an image'
    else:
        buffer = BytesIO()
        PILImage.new('RGB', (20, 20)).save(buffer, format='BMP')
        data = buffer.getvalue()
        if kind == 'pixels':
            monkeypatch.setattr(PILImage, 'MAX_IMAGE_PIXELS', 100)
        else:
            data = data[:54]

    with exceptions_context(Exceptions06()), pytest.raises(APIError) as exc:
        await ImageService.upload_avatar(data)
    assert exc.value.status_code == (413 if kind in {'bytes', 'pixels'} else 422)
    save.assert_not_awaited()
