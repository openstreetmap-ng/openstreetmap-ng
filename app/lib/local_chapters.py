from pathlib import Path
from typing import NamedTuple

import cython
import orjson


class LocalChapter(NamedTuple):
    id: str
    url: str


@cython.cfunc
def _get_local_chapters() -> list[LocalChapter]:
    resources = Path(
        'node_modules/osm-community-index/dist/resources.min.json'
    ).read_bytes()
    communities_dict: dict[str, dict] = orjson.loads(resources)['resources']

    chapters: list[LocalChapter] = [
        LocalChapter(c['id'], c['strings']['url'])
        for c in communities_dict.values()
        if c['type'] == 'osm-lc' and c['id'] != 'OSMF'
    ]
    chapters.sort(key=lambda c: c.id.casefold())
    return chapters


LOCAL_CHAPTERS = _get_local_chapters()
