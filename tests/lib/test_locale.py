import pytest

from app.lib.locale import (
    INSTALLED_LOCALES_NAMES_MAP,
    LOCALES_NAMES_MAP,
    is_installed_locale,
    normalize_locale,
)
from app.models.types import LocaleCode


def test_locales_names_sorted():
    strings = [locale_name.english.casefold() for locale_name in LOCALES_NAMES_MAP.values()]
    assert sorted(strings) == strings
    strings = [locale_name.english.casefold() for locale_name in INSTALLED_LOCALES_NAMES_MAP.values()]
    assert sorted(strings) == strings


@pytest.mark.parametrize(
    ('locale', 'expected'),
    [
        ('en', True),
        ('pl', True),
        ('EN', False),
        ('NonExistent', False),
    ],
)
def test_installed_locale(locale: str, expected: bool):
    assert is_installed_locale(LocaleCode(locale)) == expected


@pytest.mark.parametrize(
    ('locale', 'expected'),
    [
        ('en', 'en'),
        ('EN', 'en'),
        ('NonExistent', None),
    ],
)
def test_normalize_locale(locale: str, expected: str | None):
    assert normalize_locale(LocaleCode(locale)) == expected


@pytest.mark.parametrize(
    ('code', 'english', 'native', 'display_name'),
    [
        ('pl', 'polish', 'polski', 'polish (polski)'),
        ('en', 'english', 'english', 'english'),
    ],
)
def test_locales_names(code: LocaleCode, english: str, native: str, display_name: str):
    locale_name = LOCALES_NAMES_MAP[code]
    assert locale_name.english.casefold() == english
    assert locale_name.native.casefold() == native
    assert locale_name.display_name.casefold() == display_name
