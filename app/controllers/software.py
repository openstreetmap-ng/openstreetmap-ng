from typing import Annotated, TypedDict

from fastapi import APIRouter, Query

from app.lib.render_response import render_response

router = APIRouter()


class SoftwareEntry(TypedDict):
    name: str
    description: str
    url: str
    image: str
    category: str
    platforms: tuple[str, ...]
    license: str
    status: str
    highlights: tuple[str, ...]


class FilterOption(TypedDict):
    value: str
    label: str


_CATEGORIES: tuple[FilterOption, ...] = (
    {'value': 'editor', 'label': 'Editors'},
    {'value': 'mobile', 'label': 'Mobile mapping'},
    {'value': 'data', 'label': 'Data tools'},
    {'value': 'quality', 'label': 'Quality assurance'},
    {'value': 'imagery', 'label': 'Imagery'},
    {'value': 'mapmaking', 'label': 'Mapmaking'},
)

_PLATFORMS: tuple[FilterOption, ...] = (
    {'value': 'web', 'label': 'Web'},
    {'value': 'desktop', 'label': 'Desktop'},
    {'value': 'android', 'label': 'Android'},
    {'value': 'ios', 'label': 'iOS'},
)

_LICENSES: tuple[FilterOption, ...] = (
    {'value': 'open-source', 'label': 'Open source'},
    {'value': 'mixed', 'label': 'Mixed'},
    {'value': 'proprietary', 'label': 'Proprietary'},
)

_STATUSES: tuple[FilterOption, ...] = (
    {'value': 'active', 'label': 'Actively developed'},
    {'value': 'stable', 'label': 'Stable'},
    {'value': 'community', 'label': 'Community maintained'},
)

_FILTER_OPTIONS = {
    'category': _CATEGORIES,
    'platform': _PLATFORMS,
    'license': _LICENSES,
    'status': _STATUSES,
}

_FILTER_LABELS = {
    key: {option['value']: option['label'] for option in options}
    for key, options in _FILTER_OPTIONS.items()
}

_SOFTWARE: tuple[SoftwareEntry, ...] = (
    {
        'name': 'iD',
        'description': 'The default browser editor for quick OpenStreetMap edits.',
        'url': 'https://github.com/openstreetmap/iD',
        'image': '/static/img/brand/id.webp',
        'category': 'editor',
        'platforms': ('web',),
        'license': 'open-source',
        'status': 'active',
        'highlights': ('Beginner friendly', 'Built into osm.org', 'Preset-driven'),
    },
    {
        'name': 'Rapid',
        'description': 'A modern web editor with assisted mapping and validation tools.',
        'url': 'https://github.com/facebook/Rapid',
        'image': '/static/img/brand/rapid.webp',
        'category': 'editor',
        'platforms': ('web',),
        'license': 'open-source',
        'status': 'active',
        'highlights': ('Assisted mapping', 'Browser based', 'Validation tools'),
    },
    {
        'name': 'JOSM',
        'description': 'A powerful desktop editor for detailed and large-scale edits.',
        'url': 'https://josm.openstreetmap.de/',
        'image': '/static/img/brand/josm.webp',
        'category': 'editor',
        'platforms': ('desktop',),
        'license': 'open-source',
        'status': 'stable',
        'highlights': ('Advanced editing', 'Plugin ecosystem', 'Offline workflows'),
    },
    {
        'name': 'Vespucci',
        'description': 'A full OpenStreetMap editor for detailed on-device Android edits.',
        'url': 'https://vespucci.io/',
        'image': '/static/img/app.svg',
        'category': 'mobile',
        'platforms': ('android',),
        'license': 'open-source',
        'status': 'active',
        'highlights': ('Full tag editing', 'Survey workflows', 'Offline support'),
    },
    {
        'name': 'StreetComplete',
        'description': 'A quest-based Android app for adding missing local details.',
        'url': 'https://streetcomplete.app/',
        'image': '/static/img/app.svg',
        'category': 'mobile',
        'platforms': ('android',),
        'license': 'open-source',
        'status': 'active',
        'highlights': ('Simple quests', 'On-site surveys', 'No tagging knowledge needed'),
    },
    {
        'name': 'Every Door',
        'description': 'A mobile editor focused on shops, amenities, entrances, and indoor details.',
        'url': 'https://every-door.app/',
        'image': '/static/img/app.svg',
        'category': 'mobile',
        'platforms': ('android', 'ios'),
        'license': 'open-source',
        'status': 'active',
        'highlights': ('POI surveys', 'Indoor details', 'Fast field work'),
    },
    {
        'name': 'Overpass Turbo',
        'description': 'A web query interface for exploring and exporting OpenStreetMap data.',
        'url': 'https://overpass-turbo.eu/',
        'image': '/static/img/brand/overpass.webp',
        'category': 'data',
        'platforms': ('web',),
        'license': 'open-source',
        'status': 'stable',
        'highlights': ('Overpass QL', 'Map previews', 'Data export'),
    },
    {
        'name': 'Geofabrik Downloads',
        'description': 'Regional OpenStreetMap extracts for analysis, imports, and offline use.',
        'url': 'https://download.geofabrik.de/',
        'image': '/static/img/brand/geofabrik.webp',
        'category': 'data',
        'platforms': ('web',),
        'license': 'mixed',
        'status': 'stable',
        'highlights': ('Regional extracts', 'Multiple formats', 'Regular updates'),
    },
    {
        'name': 'OsmCha',
        'description': 'A review tool for finding, filtering, and triaging suspicious changesets.',
        'url': 'https://osmcha.org/',
        'image': '/static/img/app.svg',
        'category': 'quality',
        'platforms': ('web',),
        'license': 'open-source',
        'status': 'community',
        'highlights': ('Changeset review', 'Filters', 'Quality signals'),
    },
    {
        'name': 'MapRoulette',
        'description': 'A tasking platform for small, repeatable OpenStreetMap improvement jobs.',
        'url': 'https://maproulette.org/',
        'image': '/static/img/app.svg',
        'category': 'quality',
        'platforms': ('web',),
        'license': 'open-source',
        'status': 'active',
        'highlights': ('Task challenges', 'Team workflows', 'Progress tracking'),
    },
    {
        'name': 'uMap',
        'description': 'A web tool for creating custom maps with OpenStreetMap backgrounds.',
        'url': 'https://umap.openstreetmap.fr/',
        'image': '/static/img/app.svg',
        'category': 'mapmaking',
        'platforms': ('web',),
        'license': 'open-source',
        'status': 'active',
        'highlights': ('Custom layers', 'Embeds', 'Collaborative maps'),
    },
    {
        'name': 'Mapillary',
        'description': 'A street-level imagery platform frequently used by mappers during surveys.',
        'url': 'https://www.mapillary.com/',
        'image': '/static/img/app.svg',
        'category': 'imagery',
        'platforms': ('web', 'android', 'ios'),
        'license': 'proprietary',
        'status': 'active',
        'highlights': ('Street-level imagery', 'Mobile capture', 'Map data signals'),
    },
)


def _normalize_filter(value: str | None, options: tuple[FilterOption, ...]) -> str | None:
    if value is None:
        return None
    allowed = {option['value'] for option in options}
    return value if value in allowed else None


def _filter_software(
    *,
    category: str | None,
    platform: str | None,
    license_: str | None,
    status: str | None,
) -> tuple[SoftwareEntry, ...]:
    return tuple(
        entry
        for entry in _SOFTWARE
        if (category is None or entry['category'] == category)
        and (platform is None or platform in entry['platforms'])
        and (license_ is None or entry['license'] == license_)
        and (status is None or entry['status'] == status)
    )


@router.get('/software')
async def software(
    category: Annotated[str | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    license_: Annotated[str | None, Query(alias='license')] = None,
    status: Annotated[str | None, Query()] = None,
):
    selected = {
        'category': _normalize_filter(category, _CATEGORIES),
        'platform': _normalize_filter(platform, _PLATFORMS),
        'license': _normalize_filter(license_, _LICENSES),
        'status': _normalize_filter(status, _STATUSES),
    }
    entries = _filter_software(
        category=selected['category'],
        platform=selected['platform'],
        license_=selected['license'],
        status=selected['status'],
    )
    return await render_response(
        'software',
        {
            'title_prefix': 'OSM Software |',
            'entries': entries,
            'filter_options': _FILTER_OPTIONS,
            'labels': _FILTER_LABELS,
            'selected': selected,
        },
    )
