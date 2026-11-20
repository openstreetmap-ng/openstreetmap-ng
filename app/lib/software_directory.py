from typing import NamedTuple


class Software(NamedTuple):
    slug: str
    name: str
    category: str
    platforms: tuple[str, ...]
    license_type: str
    license_name: str
    maintenance: str
    website: str
    source: str


CATEGORIES = ('editing', 'navigation', 'cartography')
PLATFORMS = ('web', 'windows', 'macos', 'linux', 'android', 'ios')
LICENSES = ('open', 'proprietary')
MAINTENANCE = ('active', 'inactive')

# Curated project metadata, checked against the linked original sources on 2026-11-20.
SOFTWARE = (
    Software(
        'id',
        'iD',
        'editing',
        ('web',),
        'open',
        'ISC',
        'active',
        'https://www.openstreetmap.org/edit',
        'https://github.com/openstreetmap/iD',
    ),
    Software(
        'josm',
        'JOSM',
        'editing',
        ('windows', 'macos', 'linux'),
        'open',
        'GPL-2.0-or-later',
        'active',
        'https://josm.openstreetmap.de/',
        'https://josm.openstreetmap.de/wiki/Source%20code',
    ),
    Software(
        'organicmaps',
        'Organic Maps',
        'navigation',
        ('android', 'ios'),
        'open',
        'Apache-2.0',
        'active',
        'https://organicmaps.app/',
        'https://github.com/organicmaps/organicmaps',
    ),
    Software(
        'qgis',
        'QGIS',
        'cartography',
        ('windows', 'macos', 'linux'),
        'open',
        'GPL-2.0-or-later',
        'active',
        'https://qgis.org/',
        'https://github.com/qgis/QGIS',
    ),
)


def filter_software(
    *,
    category: str = '',
    platform: str = '',
    license_type: str = '',
    maintenance: str = '',
) -> tuple[Software, ...]:
    """Combine every selected filter; an empty value means no restriction."""
    return tuple(
        item
        for item in SOFTWARE
        if (not category or item.category == category)
        and (not platform or platform in item.platforms)
        and (not license_type or item.license_type == license_type)
        and (not maintenance or item.maintenance == maintenance)
    )
