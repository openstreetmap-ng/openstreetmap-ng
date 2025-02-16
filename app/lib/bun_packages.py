import logging
import re
from pathlib import Path

import cython
import orjson


@cython.cfunc
def _bun_versions(names: tuple[str, ...]) -> tuple[str, ...]:
    """Get the installed versions of the given JS packages."""
    names_set = set(names)
    lock_data = Path('bun.lock').read_bytes()
    lock_data = re.sub(rb',(?=\s*[]}])', b'', lock_data)  # remove trailing commas
    result: dict[str, str] = {}
    for pkg_data in orjson.loads(lock_data)['packages'].values():
        fq_name: str = pkg_data[0]
        name, _, version = fq_name.rpartition('@')
        if name in names_set:
            result[name] = version.rsplit('#', 1)[-1]  # use only commit hash if present
    return tuple(result[name] for name in names)


ID_VERSION, RAPID_VERSION = _bun_versions(('iD', '@rapideditor/rapid'))
logging.info('Packages versions: iD=%s, Rapid=%s', ID_VERSION, RAPID_VERSION)
