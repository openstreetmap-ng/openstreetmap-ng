from app.lib.image import AvatarType, Image
from app.models.types import StorageKey


def test_get_avatar_url():
    assert Image.get_avatar_url(AvatarType.default, app=False) == '/static/img/avatar.webp'
    assert Image.get_avatar_url(AvatarType.default, app=True) == '/static/img/app.webp'
    assert Image.get_avatar_url(AvatarType.gravatar, 123) == '/api/web/gravatar/123'
    assert Image.get_avatar_url(AvatarType.custom, StorageKey('123')) == '/api/web/avatar/123'
