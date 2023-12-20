import logging
import re
from collections.abc import Sequence

from cachetools import TTLCache, cached
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from config import DEFAULT_LANGUAGE
from lib.auth import auth_user
from lib.locales import normalize_locale_case
from lib.translation import translation_context
from limits import LANGUAGE_CODE_MAX_LENGTH

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language#language
# limit to matches only supported by our translation files: config/locale
_ACCEPT_LANGUAGE_RE = re.compile(r'(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?|\*)(?:;q=(?P<q>[0-9.]+))?')


@cached(TTLCache(128, ttl=86400))
def _parse_accept_language(accept_language: str) -> Sequence[str]:
    # small optimization
    if not accept_language:
        return (DEFAULT_LANGUAGE,)

    temp: list[tuple[float, str]] = []

    # process accept language codes
    for match in _ACCEPT_LANGUAGE_RE.finditer(accept_language):
        lang = match['lang']
        q = match['q']

        if (lang_len := len(lang)) > LANGUAGE_CODE_MAX_LENGTH:
            logging.debug('Accept language code is too long %d', lang_len)
            continue

        if lang == '*':
            lang = DEFAULT_LANGUAGE
        else:
            lang = normalize_locale_case(lang)
            if lang is None:
                logging.debug('Unknown accept language %r', lang)
                continue

        if q is None:
            q = 1
        else:
            try:
                q = float(q)
            except ValueError:
                logging.debug('Invalid accept language q-factor %r', q)
                continue

        temp.append((q, lang))

    # sort by q-factor, descending
    temp.sort(reverse=True)

    return tuple(lang for _, lang in temp)


class LanguageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # check user's preferred languages before parsing the accept language header
        if (user := auth_user()) and user.languages:
            languages = user.languages
        else:
            accept_language = request.headers.get('accept-language', '')
            languages = _parse_accept_language(accept_language)

        with translation_context(languages):
            return await call_next(request)
