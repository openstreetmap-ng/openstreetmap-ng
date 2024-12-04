import pytest

from app.lib.image import Image
from app.storage import GRAVATAR_STORAGE


@pytest.mark.extended
async def test_gravatar_load():
    key = 'testing@testing.invalid'
    data = await GRAVATAR_STORAGE.load(key)
    assert data == Image.default_avatar
