"""Small, editorially maintained directory; no third-party requests at page load."""

from typing import TypedDict


class Software(TypedDict):
    name: str
    url: str
    image: str
    description: str
    category: str
    platforms: tuple[str, ...]
    license: str
    status: str
    source: str


FILTERS = {
    'category': ('editing', 'analysis', 'navigation', 'tiles'),
    'platform': ('web', 'windows', 'macos', 'linux', 'android', 'ios'),
    'license': ('open', 'proprietary'),
    'status': ('maintained', 'unmaintained'),
}

SOFTWARE: tuple[Software, ...] = (
    {
        'name': 'iD',
        'url': 'https://www.openstreetmap.org/edit?editor=id',
        'image': '/static/img/brand/id.webp',
        'description': 'software.descriptions.id',
        'category': 'editing',
        'platforms': ('web',),
        'license': 'open',
        'status': 'maintained',
        'source': 'https://github.com/openstreetmap/iD',
    },
    {
        'name': 'JOSM',
        'url': 'https://josm.openstreetmap.de/',
        'image': '/static/img/brand/josm.webp',
        'description': 'software.descriptions.josm',
        'category': 'editing',
        'platforms': ('windows', 'macos', 'linux'),
        'license': 'open',
        'status': 'maintained',
        'source': 'https://josm.openstreetmap.de/wiki/Download',
    },
    {
        'name': 'Overpass turbo',
        'url': 'https://overpass-turbo.eu/',
        'image': '/static/img/brand/overpass.webp',
        'description': 'software.descriptions.overpass',
        'category': 'analysis',
        'platforms': ('web',),
        'license': 'open',
        'status': 'maintained',
        'source': 'https://github.com/tyrasd/overpass-turbo',
    },
    {
        'name': 'Organic Maps',
        'url': 'https://organicmaps.app/',
        'image': '/static/img/software/organicmaps.svg',
        'description': 'software.descriptions.organic_maps',
        'category': 'navigation',
        # Only stable mobile platforms; Linux desktop is currently beta.
        'platforms': ('android', 'ios'),
        'license': 'open',
        'status': 'maintained',
        'source': 'https://organicmaps.app/',
    },
    {
        'name': 'MapTiler Engine',
        'url': 'https://www.maptiler.com/engine/',
        'image': '/static/img/software/maptiler.svg',
        'description': 'software.descriptions.maptiler',
        'category': 'tiles',
        'platforms': ('windows', 'macos', 'linux'),
        'license': 'proprietary',
        'status': 'maintained',
        'source': 'https://docs.maptiler.com/engine/installation/',
    },
)


def normalize_filters(values: dict[str, str]):
    return {
        key: value if (value := values.get(key, '')) in options else ''
        for key, options in FILTERS.items()
    }


def filter_software(selected: dict[str, str]):
    return tuple(
        entry
        for entry in SOFTWARE
        if all(
            not value
            or (
                value in entry['platforms']
                if key == 'platform'
                else entry.get(key) == value
            )
            for key, value in normalize_filters(selected).items()
        )
    )
