import cython

from app.config import AVATAR_STORAGE_URI, BACKGROUND_STORAGE_URI, TRACE_STORAGE_URI
from app.lib.storage.base import StorageBase
from app.lib.storage.db import DBStorage
from app.lib.storage.s3 import S3Storage


@cython.cfunc
def _get_storage(uri: str) -> StorageBase:
    """
    Parse a storage URI and return the appropriate storage implementation.

    Supported URI formats:
    - Database storage: "db://avatar" -> DBStorage("avatar")
    - S3 bucket: "s3://avatar" -> S3Storage("avatar")
    """
    uri = uri.casefold()
    schema = uri[:5]
    path = uri[5:].rstrip('/')

    if schema == 'db://':
        return DBStorage(path)
    if schema == 's3://':
        return S3Storage(path)

    raise ValueError(f'Invalid storage URI: {uri}')


AVATAR_STORAGE = _get_storage(AVATAR_STORAGE_URI)
BACKGROUND_STORAGE = _get_storage(BACKGROUND_STORAGE_URI)
TRACE_STORAGE = _get_storage(TRACE_STORAGE_URI)
