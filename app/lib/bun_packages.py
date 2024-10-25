import json
import os
import subprocess
from pathlib import Path


def bun_packages(file_cache_dir: Path) -> dict[str, str]:
    """
    Get the mapping of installed packages to their versions.
    """
    bun_lock_path = Path('bun.lockb')
    bun_lock_mtime = bun_lock_path.stat().st_mtime
    cache_path = file_cache_dir / 'bun_packages.json'
    if not cache_path.is_file() or bun_lock_mtime > cache_path.stat().st_mtime:
        stdout = subprocess.check_output(('bun', 'pm', 'ls'), env={**os.environ, 'NO_COLOR': '1'}).decode()  # noqa: S603
        result: dict[str, str] = {}
        for line in stdout.splitlines()[1:]:
            _, _, line = line.partition(' ')
            package, _, version = line.rpartition('@')
            result[package] = version
        cache_path.write_text(json.dumps(result))
        os.utime(cache_path, (bun_lock_mtime, bun_lock_mtime))
    return json.loads(cache_path.read_bytes())
