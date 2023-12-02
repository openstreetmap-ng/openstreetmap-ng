from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from gettext import GNUTranslations, translation

from cachetools import TTLCache, cached
from jinja2 import Environment, FileSystemLoader

from config import LOCALE_DOMAIN
from utils import timeago

_J2 = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
    auto_reload=False,
)

# configure global filters
_J2.filters.update(
    timeago=timeago,
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


# expose translation functions to jinja2
_J2.globals.update(
    t=t,
    nt=nt,
    pt=pt,
    npt=npt,
)
