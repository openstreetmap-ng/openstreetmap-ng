from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from gettext import GNUTranslations, translation
from pathlib import Path

from app.config import DEFAULT_LANGUAGE
from app.lib.locale import is_installed_locale
from app.models.locale_name import LocaleCode

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
    if primary_locale == DEFAULT_LANGUAGE:
        processed = (primary_locale,)
    elif is_installed_locale(primary_locale):
        processed = (primary_locale, DEFAULT_LANGUAGE)
    else:
        processed = (DEFAULT_LANGUAGE,)

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


def nt(message: str, /, count: int, **kwargs) -> str:
    """
    Get the translation for the given message, with pluralization.
    """
    trans: GNUTranslations = _context.get()[1]
    translated = trans.ngettext(message, message, count)
    return translated.format(count=count, **kwargs) if len(kwargs) > 0 else translated.format(count=count)
