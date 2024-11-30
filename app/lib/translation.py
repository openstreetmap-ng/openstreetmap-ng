from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from gettext import GNUTranslations, translation
from pathlib import Path

import numpy as np

from app.lib.locale import DEFAULT_LOCALE, is_installed_locale
from app.models.types import LocaleCode

_locale_dir = Path('config/locale/gnu')
_context: ContextVar[tuple[tuple[LocaleCode, ...], GNUTranslations]] = ContextVar('TranslationContext')


# removing lru_cache will not enable live-reload for translations
# gettext always caches .mo files internally
@lru_cache(maxsize=256)
def _get_translation(locales: Iterable[LocaleCode]) -> GNUTranslations:
    """
    Get the translation object for the given languages.
    """
    return translation(
        domain='messages',
        localedir=_locale_dir,
        languages=locales,
    )


@contextmanager
def translation_context(primary_locale: LocaleCode, /):
    """
    Context manager for setting the translation in ContextVar.

    Languages order determines the preference, from most to least preferred.
    """
    processed: tuple[LocaleCode, ...]
    if primary_locale == DEFAULT_LOCALE:
        processed = (primary_locale,)
    elif is_installed_locale(primary_locale):
        processed = (primary_locale, DEFAULT_LOCALE)
    else:
        processed = (DEFAULT_LOCALE,)

    translation = _get_translation(processed)
    token = _context.set((processed, translation))
    try:
        yield
    finally:
        _context.reset(token)


def translation_locales() -> tuple[LocaleCode, ...]:
    """
    Get the locales from the translation context.

    >>> translation_locales()
    ('pl', 'en')
    """
    return _context.get()[0]


def primary_translation_locale() -> LocaleCode:
    """
    Get the primary locale from the translation context.

    >>> primary_translation_locale()
    'en'
    """
    return _context.get()[0][0]


def t(message: str, /, **kwargs) -> str:
    """
    Get the translation for the given message.
    """
    trans: GNUTranslations = _context.get()[1]
    translated = trans.gettext(message)
    return translated.format(**kwargs) if len(kwargs) > 0 else translated


def nt(message: str, /, count: int | np.integer, **kwargs) -> str:
    """
    Get the translation for the given message, with pluralization.
    """
    trans: GNUTranslations = _context.get()[1]
    translated = trans.ngettext(message, message, count)  # pyright: ignore[reportArgumentType]
    return translated.format(count=count, **kwargs) if len(kwargs) > 0 else translated.format(count=count)
