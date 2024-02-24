import logging
import re
from operator import itemgetter

import cython
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import DEFAULT_LANGUAGE
from app.lib.auth_context import auth_user
from app.lib.locale import normalize_locale
from app.lib.translation import translation_context
from app.limits import LANGUAGE_CODE_MAX_LENGTH, LANGUAGE_CODES_LIMIT

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language#language
# limit to matches only supported by our translation files: config/locale
_accept_language_re = re.compile(r'(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?|\*)(?:;q=(?P<q>[0-9.]+))?')


@cython.cfunc
def _parse_accept_language(accept_language: str) -> list[str]:
    """
    Parse the accept language header.

    Asterisk (*) is replaced with the default language.

    Returns a tuple of valid languages, from most to least preferred.

    >>> _parse_accept_language('en-US,pl;q=0.8,es;q=0.9,*;q=0.5')
    ('en-US', 'es', 'pl', 'en')
    """

    # small optimization
    if not accept_language:
        return (DEFAULT_LANGUAGE,)

    q_langs: list[tuple[float, str]] = []

    # process accept language codes
    for match in _accept_language_re.finditer(accept_language):
        lang = match['lang']
        q = match['q']

        # skip weird accept language codes
        if len(lang) > LANGUAGE_CODE_MAX_LENGTH:
            logging.debug('Accept language code is too long %d', len(lang))
            continue

        # replace asterisk with default language
        if lang == '*':
            lang = DEFAULT_LANGUAGE
        # normalize language case and check if it's supported
        else:
            try:
                lang = normalize_locale(lang, raise_on_not_found=True)
            except KeyError:
                logging.debug('Unsupported accept language %r', lang)
                continue

        # parse q-factor
        if q is None:
            q = 1
        else:
            try:
                q = float(q)
            except ValueError:
                logging.debug('Invalid accept language q-factor %r', q)
                continue

        q_langs.append((q, lang))

    # sort by q-factor, descending
    q_langs.sort(key=itemgetter(0), reverse=True)

    # remove duplicates and preserve order
    result_set: set[str] = set()
    result: list[str] = []

    for q_lang in q_langs:
        lang = q_lang[1]
        if lang not in result_set:
            result_set.add(lang)
            result.append(lang)

            if len(result) >= LANGUAGE_CODES_LIMIT:
                break

    return result


class TranslationMiddleware(BaseHTTPMiddleware):
    """
    Wrap requests in translation context.
    """

    async def dispatch(self, request: Request, call_next):
        # prefer user languages
        user = auth_user()
        languages = user.languages_valid if (user is not None) else ()

        # fallback to accept language header
        if not languages:
            accept_language = request.headers.get('Accept-Language')
            languages = _parse_accept_language(accept_language) if (accept_language is not None) else ()

        with translation_context(languages):
            return await call_next(request)
