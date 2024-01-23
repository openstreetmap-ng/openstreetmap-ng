import pathlib
from collections.abc import Sequence

import cython
import orjson

from app.config import CONFIG_DIR, DEFAULT_LANGUAGE
from app.lib.locale import normalize_locale_case
from app.lib.translation import translation_languages


@cython.cfunc
def _get_wiki_tags() -> dict[str, frozenset[str]]:
    data: dict[str, Sequence[str]] = orjson.loads(pathlib.Path(CONFIG_DIR / 'wiki_tags.json').read_bytes())
    return {
        k: frozenset(normalize_locale_case(v, raise_on_not_found=True) if v else DEFAULT_LANGUAGE)
        for k, v in data.items()
    }


_wiki_tags = _get_wiki_tags()


def tag_wiki(key: str) -> str | None:
    """
    Return a link to the wiki page for the given tag key.

    Returns None if the key is not recognized.

    >>> tag_wiki('colour')
    'https://wiki.openstreetmap.org/wiki/Key:colour?uselang=en'
    """

    locales = _wiki_tags.get(key)

    if not locales:
        return None

    user_langs = translation_languages()
    primary_lang = user_langs[0]

    # find the first user language that has a wiki page for this key
    # TODO: is uselang necessary?
    for user_lang in user_langs:
        if user_lang not in locales:
            continue
        if user_lang == DEFAULT_LANGUAGE:
            return f'https://wiki.openstreetmap.org/wiki/Key:{key}?uselang={primary_lang}'
        else:
            user_lang_case = user_lang.title()
            return f'https://wiki.openstreetmap.org/wiki/{user_lang_case}:Key:{key}?uselang={primary_lang}'

    return None
