import json
import pathlib
from collections.abc import Sequence

import cython


@cython.cfunc
def _get_local_chapters() -> tuple[tuple[str, str], ...]:
    package_dir = pathlib.Path('node_modules/osm-community-index')
    resources = (package_dir / 'dist/resources.min.json').read_bytes()
    communities_dict: dict[str, dict] = json.loads(resources)['resources']

    # filter local chapters
    chapters = [c for c in communities_dict.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF']

    # sort
    chapters.sort(key=lambda c: c['id'].casefold())

    return tuple((c['id'], c['strings']['url']) for c in chapters)


_local_chapters = _get_local_chapters()


def local_chapters() -> Sequence[tuple[str, str]]:
    """
    Get the sequence of local chapters (id, url) tuples.

    >>> local_chapters()
    [('be-chapter', 'https://openstreetmap.be'), ...]
    """

    return _local_chapters
