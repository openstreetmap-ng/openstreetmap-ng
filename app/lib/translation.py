import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from gettext import GNUTranslations, translation
from pathlib import Path

import cython
import numpy as np

from app.config import LOCALE_CODE_MAX_LENGTH
from app.lib.auth_context import auth_user
from app.lib.locale import DEFAULT_LOCALE, is_installed_locale, normalize_locale
from app.middlewares.request_context_middleware import get_request
from app.models.types import LocaleCode

_CTX = ContextVar[tuple[tuple[LocaleCode, ...], GNUTranslations]]('Translation')
_LOCALE_DIR = Path('config/locale/gnu')


# removing lru_cache will not enable live-reload for translations
# gettext always caches .mo files internally
@lru_cache(maxsize=256)
def _get_translation(locales: tuple[LocaleCode, ...]):
    """Get the translation object for the given languages."""
    return translation(
        domain='messages',
        localedir=_LOCALE_DIR,
        languages=locales,
    )


@contextmanager
def translation_context(locale: LocaleCode | None, /):
    """
    Context manager for setting the translation in ContextVar.
    Languages order determines the preference, from most to least preferred.
    Pass None to infer locale from the active request/auth context.
    """
    if locale is None:
        locale = _get_request_language()

    processed: tuple[LocaleCode, ...]
    if locale == DEFAULT_LOCALE:
        processed = (locale,)
    elif is_installed_locale(locale):
        processed = (locale, DEFAULT_LOCALE)
    else:
        processed = (DEFAULT_LOCALE,)

    token = _CTX.set((processed, _get_translation(processed)))
    try:
        yield
    finally:
        _CTX.reset(token)


@cython.cfunc
def _get_request_language():
    user = auth_user()
    if user is not None:
        return user['language']

    req = get_request()

    # Language preference of anonymous users:

    # 1. Check locale cookie
    lang_cookie = req.cookies.get('lang')
    if lang_cookie and len(lang_cookie) <= LOCALE_CODE_MAX_LENGTH:
        normalized_locale = normalize_locale(LocaleCode(lang_cookie))
        if normalized_locale is not None:
            return normalized_locale

    # 2. Check accept language header
    accept_language = req.headers.get('Accept-Language')
    if accept_language:
        return _parse_accept_language(accept_language)

    return DEFAULT_LOCALE


@lru_cache(maxsize=512)
def _parse_accept_language(accept_language: str):
    """
    Parse the accept language header.
    Returns the most preferred and supported language.

    >>> _parse_accept_language('en-US;q=0.8,*;q=0.5,pl,es;q=0.9')
    'pl'
    """
    current_q: cython.double = 0
    current_lang: LocaleCode = DEFAULT_LOCALE

    for item in accept_language.split(','):
        item = item.strip()
        if not item:
            continue

        lang_raw, _, params_raw = item.partition(';')
        lang = LocaleCode(lang_raw.strip())
        if len(lang) > LOCALE_CODE_MAX_LENGTH:
            logging.debug('Accept language code is too long %d', len(lang))
            continue

        q_num: cython.double = 1
        if params_raw:
            for param in params_raw.split(';'):
                param = param.strip()
                if not param.startswith('q='):
                    continue
                q_str = param[2:]
                try:
                    q_num = float(q_str)
                except ValueError:
                    logging.debug('Invalid accept language q-factor %r', q_str)
                    q_num = 0.0
                break

        if q_num <= current_q:
            continue

        if lang == '*':
            lang = DEFAULT_LOCALE
        else:
            lang_normal = normalize_locale(lang)
            if lang_normal is None:
                lang_prefix = LocaleCode(lang.split('-', 1)[0])
                lang_normal = normalize_locale(lang_prefix)
                if lang_normal is None:
                    logging.debug('Unsupported accept language %r', lang)
                    continue
            lang = lang_normal

        current_q = q_num
        current_lang = lang

    return current_lang


def translation_locales():
    """
    Get the locales from the translation context.

    >>> translation_locales()
    ('pl', 'en')
    """
    return _CTX.get()[0]


def primary_translation_locale():
    """
    Get the primary locale from the translation context.

    >>> primary_translation_locale()
    'en'
    """
    return _CTX.get()[0][0]


def t(message: str, /, **kwargs):
    """Get the translation for the given message."""
    trans: GNUTranslations = _CTX.get()[1]
    translated = trans.gettext(message)
    return translated.format(**kwargs) if kwargs else translated


def nt(message: str, /, count: int | np.integer, **kwargs):
    """Get the translation for the given message, with pluralization."""
    trans: GNUTranslations = _CTX.get()[1]
    translated = trans.ngettext(message, message, count)  # pyright: ignore[reportArgumentType]
    kwargs['count'] = count
    return translated.format(**kwargs)
