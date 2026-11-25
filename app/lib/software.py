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


SOFTWARE: tuple[Software, ...] = (
    {
        'name': 'JOSM',
        'url': 'https://josm.openstreetmap.de/',
        'image': 'josm.png',
        'description': 'software.josm',
        'category': 'editing',
        'platforms': ('windows', 'macos', 'linux'),
        'license': 'open',
        'status': 'active',
        'source': 'https://josm.openstreetmap.de/wiki/Download',
    },
    {
        'name': 'StreetComplete',
        'url': 'https://streetcomplete.app/',
        'image': 'streetcomplete.svg',
        'description': 'software.streetcomplete',
        'category': 'editing',
        'platforms': ('android',),
        'license': 'open',
        'status': 'active',
        'source': 'https://github.com/streetcomplete/StreetComplete',
    },
    {
        'name': 'Organic Maps',
        'url': 'https://organicmaps.app/',
        'image': 'organic-maps.jpg',
        'description': 'software.organic_maps',
        'category': 'navigation',
        'platforms': ('android', 'ios', 'linux'),
        'license': 'open',
        'status': 'active',
        'source': 'https://github.com/organicmaps/organicmaps',
    },
    {
        'name': 'QGIS',
        'url': 'https://qgis.org/',
        'image': 'qgis.svg',
        'description': 'software.qgis',
        'category': 'analysis',
        'platforms': ('windows', 'macos', 'linux'),
        'license': 'open',
        'status': 'active',
        'source': 'https://qgis.org/',
    },
)

FILTERS = {
    'category': ('editing', 'navigation', 'analysis'),
    'platform': ('windows', 'macos', 'linux', 'android', 'ios', 'web'),
    'license': ('open', 'proprietary'),
    'status': ('active', 'maintenance', 'inactive'),
}


def filter_software(filters: dict[str, str]):
    return tuple(
        entry
        for entry in SOFTWARE
        if (not filters.get('platform') or filters['platform'] in entry['platforms'])
        and (not filters.get('category') or filters['category'] == entry['category'])
        and (not filters.get('license') or filters['license'] == entry['license'])
        and (not filters.get('status') or filters['status'] == entry['status'])
    )
