import pytest

from app.lib.locale import (
    INSTALLED_LOCALES_NAMES_MAP,
    LOCALES_NAMES_MAP,
    is_installed_locale,
    normalize_locale,
)


def test_locales_names_sorted():
    strings = [locale_name.english.casefold() for locale_name in LOCALES_NAMES_MAP.values()]
    assert sorted(strings) == strings
    strings = [locale_name.english.casefold() for locale_name in INSTALLED_LOCALES_NAMES_MAP.values()]
    assert sorted(strings) == strings


@pytest.mark.parametrize(
    ('locale', 'installed'),
    [
        ('en', True),
        ('pl', True),
        ('EN', False),
        ('NonExistent', False),
    ],
)
def test_installed_locale(locale, installed):
    assert is_installed_locale(locale) == installed


@pytest.mark.parametrize(
    ('locale', 'expected'),
    [
        ('en', 'en'),
        ('EN', 'en'),
        ('NonExistent', None),
    ],
)
def test_normalize_locale(locale, expected):
    assert normalize_locale(locale) == expected


@pytest.mark.parametrize(
    ('code', 'english', 'native'),
    [
        ('pl', 'polish', 'polski'),
        ('en', 'english', 'english'),
    ],
)
def test_locales_names(code, english, native):
    locale_name = LOCALES_NAMES_MAP[code]
    assert locale_name.english.casefold() == english
    assert locale_name.native.casefold() == native
