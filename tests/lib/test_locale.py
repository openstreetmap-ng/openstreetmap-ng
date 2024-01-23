import pytest

from app.lib.locale import (
    get_all_installed_locales,
    get_all_locales_names,
    get_i18next_locale_hash_map,
    is_valid_locale,
    normalize_locale,
)


def test_is_valid_locale():
    assert is_valid_locale('en')
    assert not is_valid_locale('EN')
    assert not is_valid_locale('NonExistent')


def test_normalize_locale():
    assert normalize_locale('en') == 'en'
    assert normalize_locale('EN') == 'en'
    assert normalize_locale('NonExistent', raise_on_not_found=False) == 'NonExistent'
    with pytest.raises(KeyError):
        normalize_locale('NonExistent', raise_on_not_found=True)


def test_get_all_installed_locales():
    locales = get_all_installed_locales()
    assert 'en' in locales
    assert 'pl' in locales


def test_get_all_locales_names():
    names = get_all_locales_names()
    pl = next(name for name in names if name.code == 'pl')
    assert pl.english.casefold() == 'polish'
    assert pl.native.casefold() == 'polski'


def test_get_i18next_locale_hash_map():
    hash_map = get_i18next_locale_hash_map()
    assert 'en' in hash_map
    assert 'pl' in hash_map
