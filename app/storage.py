from app.libc.storage.gravatar import GravatarStorage
from app.libc.storage.local import LocalStorage

AVATAR_STORAGE = LocalStorage('avatar')
GRAVATAR_STORAGE = GravatarStorage()
TRACES_STORAGE = LocalStorage('traces')
