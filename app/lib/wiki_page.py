import pathlib
from collections.abc import Sequence

import cython
import orjson

from app.config import CONFIG_DIR, DEFAULT_LANGUAGE
from app.lib.locale import normalize_locale
from app.lib.translation import translation_languages


@cython.cfunc
def _get_wiki_pages() -> dict[str, frozenset[str]]:
    data: dict[str, Sequence[str]] = orjson.loads(pathlib.Path(CONFIG_DIR / 'wiki_pages.json').read_bytes())
    return {
        tag: frozenset(
            normalize_locale(locale, raise_on_not_found=True)  #
            if locale
            else DEFAULT_LANGUAGE
            for locale in locales
        )
        for tag, locales in data.items()
    }


# mapping of tags/keys, to a set of locales that have a wiki page
_wiki_pages = _get_wiki_pages()


# TODO: perhaps support glob matches: Key:*:lanes


def wiki_page(tag_key: str, tag_value: str) -> str | None:
    """
    Return a link to the wiki page for the given tag.

    Returns None if the tag is not recognized.

    >>> wiki_page('colour')
    'https://wiki.openstreetmap.org/wiki/Key:colour?uselang=en'
    """

    # check for tag first (more specific)
    wiki_page_tag = f'Tag:{tag_key}={tag_value}'
    wiki_page_key = f'Key:{tag_key}'

    for page in (wiki_page_tag, wiki_page_key):
        locales = _wiki_pages.get(page)

        # if the page doesn't exist, skip it
        if locales is None:
            continue

        user_langs = translation_languages()

        # prioritize wiki pages that match the user's language preferences
        # user_langs always include the default language
        # TODO: is uselang necessary?
        for user_lang in user_langs:
            if user_lang not in locales:
                continue

            if user_lang == DEFAULT_LANGUAGE:
                primary_lang = user_langs[0]
                return f'https://wiki.openstreetmap.org/wiki/{page}?uselang={primary_lang}'
            else:
                user_lang_case = user_lang.title()
                primary_lang = user_langs[0]
                return f'https://wiki.openstreetmap.org/wiki/{user_lang_case}:{page}?uselang={primary_lang}'

    return None
