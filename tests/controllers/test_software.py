from app.controllers.software import (
    _CATEGORIES,
    _filter_software,
    _normalize_filter,
)


def _names(entries):
    return {entry['name'] for entry in entries}


def test_normalize_filter_rejects_unknown_values():
    assert _normalize_filter('missing', _CATEGORIES) is None


def test_filter_software_by_platform_and_license():
    names = _names(
        _filter_software(
            category=None,
            platform='android',
            license_='open-source',
            status=None,
        )
    )

    assert 'StreetComplete' in names
    assert 'Vespucci' in names
    assert 'Mapillary' not in names


def test_filter_software_by_category_and_status():
    names = _names(
        _filter_software(
            category='quality',
            platform=None,
            license_=None,
            status='active',
        )
    )

    assert names == {'MapRoulette'}
