import pytest

from app.lib.locale import (
    get_all_installed_locales,
    get_all_locales_names,
    is_valid_locale,
    normalize_locale,
)


@pytest.mark.parametrize('locale', ['en', 'pl'])
def test_valid_locale(locale):
    assert is_valid_locale(locale)


@pytest.mark.parametrize('locale', ['EN', 'NonExistent'])
def test_invalid_locale(locale):
    assert not is_valid_locale(locale)


@pytest.mark.parametrize(('locale', 'expected'), [('en', 'en'), ('EN', 'en'), ('NonExistent', None)])
def test_normalize_locale(locale, expected):
    assert normalize_locale(locale) == expected


@pytest.mark.parametrize('locale', ['en', 'pl'])
def test_installed_locales(locale):
    assert locale in get_all_installed_locales()


@pytest.mark.parametrize(
    ('code', 'english', 'native'),
    [
        ('pl', 'polish', 'polski'),
        ('en', 'english', 'english'),
    ],
)
def test_locales_names(code, english, native):
    names = get_all_locales_names()
    pl = next(name for name in names if name.code == code)
    assert pl.english.casefold() == english
    assert pl.native.casefold() == native
