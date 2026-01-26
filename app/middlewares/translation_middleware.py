import logging
from functools import lru_cache

import cython
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import LOCALE_CODE_MAX_LENGTH
from app.lib.auth_context import auth_user
from app.lib.locale import DEFAULT_LOCALE, normalize_locale
from app.lib.translation import translation_context
from app.middlewares.request_context_middleware import get_request
from app.models.types import LocaleCode


class TranslationMiddleware:
    """Wrap requests in translation context."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        with translation_context(_get_request_language()):
            return await self.app(scope, receive, send)


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
                    q_num = 0
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
