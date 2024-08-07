from app.lib.storage.gravatar import GravatarStorage
from app.lib.storage.local import LocalStorage

AVATAR_STORAGE = LocalStorage('avatar')
BACKGROUND_STORAGE = LocalStorage('background')
GRAVATAR_STORAGE = GravatarStorage()
TRACES_STORAGE = LocalStorage('traces')
