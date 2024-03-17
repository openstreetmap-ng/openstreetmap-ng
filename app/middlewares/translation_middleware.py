import logging
import re
from functools import lru_cache
from operator import itemgetter

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import DEFAULT_LANGUAGE
from app.lib.auth_context import auth_user
from app.lib.locale import normalize_locale
from app.lib.translation import translation_context
from app.limits import LANGUAGE_CODE_MAX_LENGTH, LANGUAGE_CODES_LIMIT
from app.middlewares.request_context_middleware import get_request

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language#language
# limit to matches only supported by our translation files: config/locale
_accept_language_re = re.compile(r'(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?|\*)(?:;q=(?P<q>[0-9.]+))?')


@lru_cache(maxsize=512)
def _parse_accept_language(accept_language: str) -> tuple[str, ...]:
    """
    Parse the accept language header.

    Asterisk (*) is replaced with the default language.

    Returns a tuple of valid languages, from most to least preferred.

    >>> _parse_accept_language('en-US,pl;q=0.8,es;q=0.9,*;q=0.5')
    ('en-US', 'es', 'pl', 'en')
    """

    q_langs: list[tuple[float, str]] = []

    # process accept language codes
    for match in _accept_language_re.finditer(accept_language):
        lang: str = match['lang']

        # skip weird accept language codes
        if len(lang) > LANGUAGE_CODE_MAX_LENGTH:
            logging.debug('Accept language code is too long %d', len(lang))
            continue

        # replace asterisk with default language
        if lang == '*':
            lang = DEFAULT_LANGUAGE
        # normalize language case and check if it's supported
        else:
            lang_normal = normalize_locale(lang)
            if lang_normal is None:
                if lang != 'en-US':  # reduce logging noise
                    logging.debug('Unsupported accept language %r', lang)
                continue
            lang = lang_normal

        q: str | None = match['q']

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

    return tuple(result)


class TranslationMiddleware:
    """
    Wrap requests in translation context.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        # prefer user languages
        user = auth_user()
        languages = user.languages_valid if (user is not None) else ()

        # fallback to accept language header
        if not languages:
            request = get_request()
            accept_language = request.headers.get('Accept-Language')
            languages = _parse_accept_language(accept_language) if accept_language else ()

        with translation_context(languages):
            await self.app(scope, receive, send)
