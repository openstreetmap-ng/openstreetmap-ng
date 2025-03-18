import pytest

from app.lib.image import DEFAULT_USER_AVATAR
from app.models.types import Email
from app.queries.gravatar_query import GravatarQuery


@pytest.mark.extended
async def test_gravatar_load():
    email = Email('testing@testing.invalid')
    data = await GravatarQuery.load(email)
    assert data == DEFAULT_USER_AVATAR, 'Default avatar must be returned when Gravatar is not found'
