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
def _get_wiki_pages() -> dict[str, frozenset[str]]:
    data: dict[str, Sequence[str]] = json.loads(pathlib.Path(CONFIG_DIR / 'wiki_pages.json').read_bytes())
    return {
        tag: frozenset(
            normalize_locale(locale)
            if locale  #
            else DEFAULT_LANGUAGE
            for locale in locales
        )
        for tag, locales in data.items()
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

        is_value: cython.char
        for is_value in (True, False):
            if is_value:
                tag_values = tag.values
                tag_value = tag_values[0]

                # skip if already styled
                if tag_value.format is not None or len(tag_values) != 1:
                    continue

                page = f'Tag:{tag_key.value}={tag_value.value}'
            else:
                # skip if already styled
                if tag_key.format is not None:
                    continue

                page = f'Key:{tag_key.value}'

            locales = _wiki_pages.get(page)
            if locales is None:  # page does not exist
                continue

            # prioritize wiki pages that match the user's language preferences
            # user_langs always include the default language
            # TODO: is uselang necessary?
            for user_lang in user_langs:
                if user_lang not in locales:
                    continue

                if user_lang == DEFAULT_LANGUAGE:
                    url = f'https://wiki.openstreetmap.org/wiki/{page}?uselang={primary_lang}'
                else:
                    user_lang_case = user_lang.title()
                    url = f'https://wiki.openstreetmap.org/wiki/{user_lang_case}:{page}?uselang={primary_lang}'

                if is_value:
                    tag.values = (TagFormat(tag_value.value, 'url-safe', url),)
                else:
                    tag.key = TagFormat(tag_key.value, 'url-safe', url)

                break
