import cython

from app.config import AVATAR_STORAGE_URL, BACKGROUND_STORAGE_URL, TRACE_STORAGE_URL
from app.lib.storage.db import DBStorage
from app.lib.storage.s3 import S3Storage


@cython.cfunc
def _get_storage(url: str):
    """
    Parse a storage URL and return the appropriate storage implementation.

    Supported URL formats:
    - Database storage: "db://avatar" -> DBStorage("avatar")
    - S3 bucket: "s3://avatar" -> S3Storage("avatar")
    """
    scheme = url[:5]
    path = url[5:].rstrip('/')

    if scheme == 'db://':
        return DBStorage(path)
    if scheme == 's3://':
        return S3Storage(path)

    raise ValueError(f'Invalid storage URL: {url}')


AVATAR_STORAGE = _get_storage(AVATAR_STORAGE_URL)
BACKGROUND_STORAGE = _get_storage(BACKGROUND_STORAGE_URL)
TRACE_STORAGE = _get_storage(TRACE_STORAGE_URL)
