import pathlib

import cython
import orjson


@cython.cfunc
def _get_local_chapters_ids() -> frozenset[str]:
    package_dir = pathlib.Path('node_modules/osm-community-index')
    resources = (package_dir / 'dist/resources.min.json').read_bytes()
    communities_dict: dict[str, dict] = orjson.loads(resources)['resources']

    # filter only local chapters
    ids = (c['id'] for c in communities_dict.values() if c['type'] == 'osm-lc' and c['id'] != 'OSMF')

    return frozenset(sorted(ids))


_local_chapters_ids = _get_local_chapters_ids()


def local_chapters_ids() -> frozenset[str]:
    """
    Get the set of local chapters IDs.

    >>> local_chapters_ids()
    {'be-chapter', 'cd-chapter', ...}
    """

    return _local_chapters_ids
