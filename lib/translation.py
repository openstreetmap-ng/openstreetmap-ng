from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from gettext import GNUTranslations, translation

from cachetools import TTLCache, cached
from jinja2 import Environment, FileSystemLoader

from config import LOCALE_DOMAIN

_J2 = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
    auto_reload=False,
    extensions=['jinja2.ext.i18n'],
)  # TODO: extensions in overlay? possible cache issue?

_context = ContextVar('Translation_context')


@cached(TTLCache(128, ttl=86400))
def _get_translation(languages: Sequence[str]) -> GNUTranslations:
    return translation(
        domain=LOCALE_DOMAIN,
        localedir='config/locale',
        languages=languages,
    )


@cached(TTLCache(128, ttl=3600))
def _get_j2(t: GNUTranslations) -> Environment:
    j2 = _J2.overlay()
    j2.install_gettext_translations(t, newstyle=True)
    return j2


@contextmanager
def translation_context(languages: Sequence[str]):
    """
    Context manager for setting the translation in ContextVar.

    Languages order determines the preference, from most to least preferred.
    """

    t = _get_translation(languages)
    j2 = _get_j2(t)
    token = _context.set((t, j2))
    try:
        yield
    finally:
        _context.reset(token)


def gettext(message: str) -> str:
    """
    Get the translation for the given message.
    """

    t: GNUTranslations = _context.get()[0]
    return t.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """
    Get the translation for the given message, with pluralization.
    """

    t: GNUTranslations = _context.get()[0]
    return t.ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    """
    Get the translation for the given message, with context.
    """

    t: GNUTranslations = _context.get()[0]
    return t.pgettext(context, message)


def npgettext(context: str, singular: str, plural: str, n: int) -> str:
    """
    Get the translation for the given message, with context and pluralization.
    """

    t: GNUTranslations = _context.get()[0]
    return t.npgettext(context, singular, plural, n)


def render(template_name: str, **template_data: dict) -> str:
    """
    Render the given Jinja2 template with translation.
    """

    j2: Environment = _context.get()[1]
    return j2.get_template(template_name).render(**template_data)
