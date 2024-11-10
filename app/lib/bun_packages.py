import logging
import os
import subprocess
from pathlib import Path

import cython
import orjson

from app.config import FILE_CACHE_DIR


@cython.cfunc
def _bun_packages() -> dict[str, str]:
    """
    Get the mapping of installed packages to their versions.
    """
    lock_path = Path('bun.lockb')
    lock_mtime = lock_path.stat().st_mtime
    cache_path = FILE_CACHE_DIR / 'bun_packages.json'
    if not cache_path.is_file() or lock_mtime > cache_path.stat().st_mtime:
        stdout = subprocess.check_output(('bun', 'pm', 'ls'), env={**os.environ, 'NO_COLOR': '1'}).decode()  # noqa: S603
        result: dict[str, str] = {}
        for line in stdout.splitlines()[1:]:
            _, _, line = line.partition(' ')
            package, _, version = line.rpartition('@')
            result[package] = version
        cache_path.write_bytes(orjson.dumps(result))
        os.utime(cache_path, (lock_mtime, lock_mtime))
    return orjson.loads(cache_path.read_bytes())


_data = _bun_packages()
ID_VERSION = _data['iD'].rpartition('#')[2]
RAPID_VERSION = _data['@rapideditor/rapid']
logging.info('Packages versions: iD=%s, Rapid=%s', ID_VERSION, RAPID_VERSION)
del _data
