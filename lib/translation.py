from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from gettext import GNUTranslations, translation

import arrow
from cachetools import TTLCache, cached
from jinja2 import Environment, FileSystemLoader

from config import DEFAULT_LANGUAGE, LOCALE_DOMAIN
from utils import format_iso_date, utcnow

_J2 = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
    auto_reload=False,
)

_context_langs = ContextVar('Translation_context_langs')
_context_trans = ContextVar('Translation_context_trans')


@cached(TTLCache(128, ttl=86400))
def _get_translation(languages: Sequence[str]) -> GNUTranslations:
    return translation(
        domain=LOCALE_DOMAIN,
        localedir='config/locale',
        languages=languages,
    )


@contextmanager
def translation_context(languages: Sequence[str]):
    """
    Context manager for setting the translation in ContextVar.

    Languages order determines the preference, from most to least preferred.
    """

    # always use default translation language
    languages = tuple(*languages, DEFAULT_LANGUAGE)

    trans = _get_translation(languages)
    token_langs = _context_langs.set(languages)
    token_trans = _context_trans.set(trans)
    try:
        yield
    finally:
        _context_langs.reset(token_langs)
        _context_trans.reset(token_trans)


def translation_languages() -> Sequence[str]:
    """
    Get the languages from the translation context.
    """

    return _context_langs.get()


def t(message: str, **kwargs) -> str:
    """
    Get the translation for the given message.
    """

    trans: GNUTranslations = _context_trans.get()
    return trans.gettext(message).format(**kwargs)


def nt(singular: str, plural: str, n: int, **kwargs) -> str:
    """
    Get the translation for the given message, with pluralization.
    """

    trans: GNUTranslations = _context_trans.get()
    return trans.ngettext(singular, plural, n).format(**kwargs)


def pt(context: str, message: str, **kwargs) -> str:
    """
    Get the translation for the given message, with context.
    """

    trans: GNUTranslations = _context_trans.get()
    return trans.pgettext(context, message).format(**kwargs)


def npt(context: str, singular: str, plural: str, n: int, **kwargs) -> str:
    """
    Get the translation for the given message, with context and pluralization.
    """

    trans: GNUTranslations = _context_trans.get()
    return trans.npgettext(context, singular, plural, n).format(**kwargs)


def render(template_name: str, **template_data: dict) -> str:
    """
    Render the given Jinja2 template with translation.
    """

    return _J2.get_template(template_name).render(**template_data)


def timeago(date: datetime, *, html: bool = False) -> str:
    """
    Get a human-readable time difference from the given date.

    Optionally, return the result as an HTML <time> element.

    >>> timeago(datetime(2021, 12, 31, 15, 30, 45))
    'an hour ago'

    >>> timeago(datetime(2021, 12, 31, 15, 30, 45), html=True)
    '<time datetime="2021-12-31T15:30:45Z" title="31 December 2021 at 15:30">an hour ago</time>'
    """

    now = utcnow()
    locale = translation_languages()[0]
    ago = arrow.get(date).humanize(now, locale=locale)

    if html:
        datetime_ = format_iso_date(date)
        title = date.strftime('%d %B %Y at %H:%M')
        return f'<time datetime="{datetime_}" title="{title}">{ago}</time>'
    else:
        return ago


# configure globals and filters
_J2.globals.update(
    t=t,
    nt=nt,
    pt=pt,
    npt=npt,
)

_J2.filters.update(
    timeago=timeago,
)
