import pytest

from app.lib.legal import legal_terms


@pytest.mark.parametrize('locale', ['FR', 'GB', 'IT'])
def test_legal_terms(locale):
    assert '<ol start="8">' in legal_terms(locale)


def test_legal_terms_not_found():
    with pytest.raises(KeyError):
        legal_terms('NonExistent')
