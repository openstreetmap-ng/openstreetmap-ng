from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from functools import lru_cache
from gettext import GNUTranslations, translation

import cython
from jinja2 import Environment, FileSystemLoader

from app.config import DEFAULT_LANGUAGE, LOCALE_DIR, TEST_ENV
from app.lib.date_utils import format_iso_date, utcnow

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil

_locale_dir = LOCALE_DIR / 'gnu'

_j2 = Environment(
    loader=FileSystemLoader('app/templates'),
    keep_trailing_newline=True,
    autoescape=True,
    # cache templates in production
    cache_size=0 if TEST_ENV else -1,
    auto_reload=False,
)

_context_langs = ContextVar('Translation_context_langs')
_context_trans = ContextVar('Translation_context_trans')


# removing this will not enable live-reload for translations
# gettext always caches .mo files internally
@lru_cache(maxsize=128)
def _get_translation(languages: Sequence[str]) -> GNUTranslations:
    """
    Get the translation object for the given languages.
    """

    return translation(
        domain='messages',
        localedir=_locale_dir,
        languages=languages,
    )


@contextmanager
def translation_context(languages: Sequence[str]):
    """
    Context manager for setting the translation in ContextVar.

    Languages order determines the preference, from most to least preferred.
    """

    processed = []
    default_lang = DEFAULT_LANGUAGE  # read property once for performance

    for lang in languages:
        processed.append(lang)

        # small optimization, abort if the default language is reached
        if lang == default_lang:
            break
    else:
        # processed languages must contain the default language
        processed.append(default_lang)

    trans = _get_translation(processed)
    token_langs = _context_langs.set(processed)
    token_trans = _context_trans.set(trans)
    try:
        yield
    finally:
        _context_langs.reset(token_langs)
        _context_trans.reset(token_trans)


def translation_languages() -> Sequence[str]:
    """
    Get the languages from the translation context.

    >>> translation_languages()
    ('en', 'pl')
    """

    return _context_langs.get()


def primary_translation_language() -> str:
    """
    Get the primary language from the translation context.

    >>> primary_translation_language()
    'en'
    """

    return _context_langs.get()[0]


def t(message: str, **kwargs) -> str:
    """
    Get the translation for the given message.
    """

    trans: GNUTranslations = _context_trans.get()
    translated = trans.gettext(message)
    return translated.format(**kwargs) if len(kwargs) > 0 else translated


def nt(message: str, count: int, **kwargs) -> str:
    """
    Get the translation for the given message, with pluralization.
    """

    trans: GNUTranslations = _context_trans.get()
    translated = trans.ngettext(message, message, count)
    return translated.format(count=count, **kwargs) if len(kwargs) > 0 else translated.format(count=count)


def render(template_name: str, **template_data: dict) -> str:
    """
    Render the given Jinja2 template with translation.
    """

    return _j2.get_template(template_name).render(**template_data)


def timeago(date: datetime, *, html: bool = False) -> str:
    """
    Get a human-readable time difference from the given date.

    Optionally, return the result as an HTML <time> element.

    >>> timeago(datetime(2021, 12, 31, 15, 30, 45))
    'an hour ago'

    >>> timeago(datetime(2021, 12, 31, 15, 30, 45), html=True)
    '<time datetime="2021-12-31T15:30:45Z" title="31 December 2021 at 15:30">an hour ago</time>'
    """

    total_seconds: cython.double = (utcnow() - date).total_seconds()

    if total_seconds < 1:
        # less than 1 second ago
        ago = nt('datetime.distance_in_words_ago.less_than_x_seconds', 1)
    elif total_seconds < 30:
        # X seconds ago
        ago = nt('datetime.distance_in_words_ago.x_seconds', ceil(total_seconds))
    elif total_seconds < 45:
        # half a minute ago
        ago = t('datetime.distance_in_words_ago.half_a_minute')
    elif total_seconds < 60:
        # less than a minute ago
        ago = nt('datetime.distance_in_words_ago.less_than_x_minutes', 1)
    elif total_seconds < 3600:
        # X minutes ago
        ago = nt('datetime.distance_in_words_ago.x_minutes', int(total_seconds / 60))
    elif total_seconds < (3600 * 24):
        # about X hours ago
        ago = nt('datetime.distance_in_words_ago.about_x_hours', int(total_seconds / 3600))
    elif total_seconds < (3600 * 24 * 30):
        # X days ago
        ago = nt('datetime.distance_in_words_ago.x_days', int(total_seconds / (3600 * 24)))
    elif total_seconds < (3600 * 24 * 330):
        # X months ago
        ago = nt('datetime.distance_in_words_ago.x_months', int(total_seconds / (3600 * 24 * 30)))
    else:
        if total_seconds % (3600 * 24 * 365) < (3600 * 24 * 330):
            # X years ago
            ago = nt('datetime.distance_in_words_ago.x_years', int(total_seconds / (3600 * 24 * 365)))
        else:
            # almost X years ago
            ago = nt('datetime.distance_in_words_ago.almost_x_years', int(ceil(total_seconds / (3600 * 24 * 365))))

    if html:
        iso_date = format_iso_date(date)
        friendly_date = date.strftime(t('time.formats.friendly'))
        return f'<time datetime="{iso_date}" title="{friendly_date}">{ago}</time>'
    else:
        return ago


# configure template globals
_j2.globals.update(t=t, nt=nt)

# configure template filters
_j2.filters.update(timeago=timeago)
