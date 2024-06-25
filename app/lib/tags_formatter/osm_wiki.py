import json
import pathlib
from collections.abc import Sequence

import cython

from app.config import CONFIG_DIR, DEFAULT_LANGUAGE
from app.lib.locale import normalize_locale
from app.lib.translation import translation_languages
from app.models.tag_format import TagFormat, TagFormatCollection

# TODO: perhaps support glob matches: Key:*:lanes


@cython.cfunc
def _get_wiki_pages() -> dict[tuple[str, str], frozenset[str]]:
    data = json.loads(pathlib.Path(CONFIG_DIR / 'wiki_pages.json').read_bytes())
    return {
        (key, value): frozenset(
            normalize_locale(locale)
            if locale  #
            else DEFAULT_LANGUAGE
            for locale in locales
        )
        for key, value_locales in data.items()
        for value, locales in value_locales.items()
    }


# mapping of tags/keys, to a set of locales that have a wiki page
_wiki_pages = _get_wiki_pages()


def tags_format_osm_wiki(tags: Sequence[TagFormatCollection]) -> None:
    """
    Format tags with supported wiki links.
    """
    user_langs = translation_languages()
    primary_lang = user_langs[0]

    for tag in tags:
        tag_key = tag.key
        key = tag_key.value

        specific: cython.char
        for specific in (True, False):
            if specific:
                tag_values = tag.values
                tag_value = tag_values[0]

                # skip already styled
                # TODO: support styling multiple values
                if tag_value.format is not None or len(tag_values) != 1:
                    continue

                value = tag_value.value
            else:
                # skip already styled
                if tag_key.format is not None:
                    continue

                value = '*'

            locales = _wiki_pages.get((key, value))
            if locales is None:
                continue

            page = f'Tag:{key}={value}' if specific else f'Key:{key}'

            # prioritize wiki pages that match the user's language preferences
            for user_lang in user_langs:
                if user_lang not in locales:
                    continue

                if user_lang == DEFAULT_LANGUAGE:
                    url = f'https://wiki.openstreetmap.org/wiki/{page}'
                else:
                    user_lang_case = user_lang.title()
                    url = f'https://wiki.openstreetmap.org/wiki/{user_lang_case}:{page}'

                if specific:
                    tag.values = (TagFormat(tag_value.value, 'url-safe', url),)
                else:
                    tag.key = TagFormat(tag_key.value, 'url-safe', url)

                break
