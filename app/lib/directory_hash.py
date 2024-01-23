import hashlib
import pathlib
from base64 import urlsafe_b64encode


def directory_hash(path) -> str:
    """
    Get a hash of the contents of a directory.

    >>> directory_hash('config/locale/frontend')
    'xJoyDvdoH4Q='
    """

    hasher = hashlib.sha256()

    for p in sorted(pathlib.Path(path).iterdir()):
        if not p.is_file():
            raise ValueError(f'{p!r} is not a file')

        hasher.update(p.read_bytes())

    return urlsafe_b64encode(hasher.digest()[:8]).decode()
