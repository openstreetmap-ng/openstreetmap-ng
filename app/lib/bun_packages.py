import os
import subprocess


def bun_packages() -> dict[str, str]:
    """
    Get the mapping of installed packages to their versions.
    """
    stdout = subprocess.check_output(('bun', 'pm', 'ls'), env={**os.environ, 'NO_COLOR': '1'}).decode()  # noqa: S603
    result: dict[str, str] = {}
    for line in stdout.splitlines()[1:]:
        _, _, line = line.partition(' ')
        package, _, version = line.rpartition('@')
        result[package] = version
    return result
