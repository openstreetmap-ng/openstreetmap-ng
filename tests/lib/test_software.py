from pathlib import Path
from urllib.parse import urlsplit

from app.lib.software import FILTERS, SOFTWARE, filter_software, normalize_filters


def test_software_combined_filters():
    assert filter_software({}) == SOFTWARE
    assert [
        entry['name']
        for entry in filter_software({
            'platform': 'windows',
            'category': 'tiles',
            'license': 'proprietary',
            'status': 'maintained',
        })
    ] == ['MapTiler Engine']
    assert [
        entry['name']
        for entry in filter_software({'platform': 'web', 'category': 'editing'})
    ] == ['iD']
    assert [
        entry['name']
        for entry in filter_software({'platform': 'android', 'license': 'open'})
    ] == ['Organic Maps']
    assert filter_software({'platform': 'android', 'license': 'proprietary'}) == ()
    assert filter_software({'status': 'unmaintained'}) == ()


def test_software_unknown_filters():
    assert filter_software({'platform': '<script>', 'unexpected': 'x'}) == SOFTWARE
    assert normalize_filters({'license': 'open', 'status': 'garbage'}) == {
        'category': '',
        'platform': '',
        'license': 'open',
        'status': '',
    }


def test_software_catalog_integrity():
    assert len({entry['name'] for entry in SOFTWARE}) == len(SOFTWARE)
    for entry in SOFTWARE:
        assert entry['description'].startswith('software.descriptions.')
        for key in ('category', 'license', 'status'):
            assert entry[key] in FILTERS[key]
        assert entry['platforms']
        assert set(entry['platforms']) <= set(FILTERS['platform'])
        assert entry['image'].startswith('/static/img/')
        assert Path('app' + entry['image']).is_file()
        for key in ('url', 'source'):
            url = urlsplit(entry[key])
            assert url.scheme == 'https' and url.netloc
