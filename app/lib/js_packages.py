import logging
from pathlib import Path

import cython
import yaml


@cython.cfunc
def _pnpm_versions(names: tuple[str, ...], /) -> list[str]:
    """Get the installed versions of the given JS packages."""
    names_set = set(names)
    result: dict[str, str] = {}
    data: dict = yaml.load(Path('pnpm-lock.yaml').read_bytes(), yaml.CSafeLoader)

    for pkg_data in data['packages']:
        fq_name: str = pkg_data[0]
        name, _, version = fq_name.rpartition('@')
        if name in names_set:
            result[name] = version.rsplit('#', 1)[-1]  # use only commit hash if present

    return [result[name] for name in names]


ID_VERSION, RAPID_VERSION = 'abc', 'def'
logging.info('Packages versions: iD=%s, Rapid=%s', ID_VERSION, RAPID_VERSION)
