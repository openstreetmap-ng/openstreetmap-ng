import hashlib
import logging
import pathlib
from base64 import urlsafe_b64encode


def directory_hash(path, *, strict: bool) -> str:
    """
    Get a hash of the contents of a directory.

    If strict is True, raise an exception if the directory does not exist.

    >>> directory_hash('config/locale/frontend')
    'xJoyDvdoH4Q='
    """

    hasher = hashlib.sha256()

    try:
        for p in sorted(pathlib.Path(path).iterdir()):
            if not p.is_file():
                raise ValueError(f'{p!r} is not a file')

            hasher.update(p.read_bytes())

        return urlsafe_b64encode(hasher.digest()[:8]).decode()

    except FileNotFoundError:
        if strict:
            raise

        logging.warning('Could not find directory to hash %r', path)
        return 'NOT_FOUND'
