from app.lib.storage.gravatar import GravatarStorage
from app.lib.storage.local import LocalStorage

AVATAR_STORAGE = LocalStorage('avatar')
GRAVATAR_STORAGE = GravatarStorage()
TRACKS_STORAGE = LocalStorage('tracks')
