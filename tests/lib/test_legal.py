import pytest

from app.lib.legal import get_legal_terms


def test_legal_terms_format():
    must_contain = '<ol start="8">'

    for locale in ('FR', 'GB', 'IT'):
        html = get_legal_terms(locale)
        assert must_contain in html


def test_legal_terms_throw_on_missing():
    with pytest.raises(KeyError):
        get_legal_terms('NonExistent')
