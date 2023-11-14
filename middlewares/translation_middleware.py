import logging
import re
from typing import Sequence

from cachetools import TTLCache, cached
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from config import DEFAULT_LANGUAGE
from lib.locales import normalize_locale_case
from lib.translation import get_translation

_accept_language_re = re.compile(r'(?P<lang>[a-zA-Z]{1,8}(?:-[a-zA-Z0-9]{1,8})?|\*)(?:;q=(?P<q>[0-9.]+))?', re.X)


@cached(TTLCache(128, ttl=86400))
def _parse_accept_language(accept_language: str) -> Sequence[str]:
    temp: list[tuple[float, str]] = []

    for match in _accept_language_re.finditer(accept_language):
        lang = match.group('lang')

        if (lang_len := len(lang)) > 10:
            logging.debug('Too long accept language %d', lang_len)
            continue

        if lang == '*':
            lang = DEFAULT_LANGUAGE
        else:
            lang = normalize_locale_case(lang)
            if lang is None:
                logging.debug('Unknown accept language %r', lang)
                continue

        q = match.group('q')

        if q is None:
            q = 1
        else:
            try:
                q = float(q)
            except ValueError:
                logging.debug('Invalid accept language q-factor %r', q)
                continue

        temp.append((q, lang))

    temp.append((0, DEFAULT_LANGUAGE))
    temp.sort(reverse=True)  # sort by q-factor, descending

    return tuple(lang for _, lang in temp)


class LanguageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # TODO: user preference

        accept_language = request.headers.get('accept-language', '')
        languages = _parse_accept_language(accept_language)

        request.state.languages = languages
        request.state.t = get_translation(languages)

        return await call_next(request)
