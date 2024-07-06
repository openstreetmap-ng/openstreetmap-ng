import json
from collections.abc import Iterable
from pathlib import Path

import cython

from app.config import DEFAULT_LANGUAGE
from app.lib.locale import normalize_locale
from app.lib.translation import translation_languages
from app.models.tag_format import TagFormat, ValueFormat

# TODO: perhaps support glob matches: Key:*:lanes


@cython.cfunc
def _get_wiki_pages() -> dict[tuple[str, str], frozenset[str | None]]:
    data = json.loads(Path('config/wiki_pages.json').read_bytes())
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


# mapping of tags to a set of locales that have a wiki page
_wiki_pages = _get_wiki_pages()


def tags_format_osm_wiki(tags: Iterable[TagFormat]) -> None:
    """
    Format tags with supported wiki links.
    """
    user_langs = translation_languages()
    for tag in tags:
        key = tag.key.text
        tag.key = _transform(
            user_langs=user_langs,
            key=key,
            processing_values=False,
            value=tag.key,
        )
        tag.values = [
            _transform(
                user_langs=user_langs,
                key=key,
                processing_values=True,
                value=value,
            )
            for value in tag.values
        ]


@cython.cfunc
def _transform(
    *,
    user_langs: Iterable[str],
    key: str,
    processing_values: cython.char,
    value: ValueFormat,
):
    # skip already styled
    if value.format is not None:
        return value

    wiki_locales = _wiki_pages.get((key, value.text) if processing_values else (key, '*'))
    if wiki_locales is None:
        return value

    page = f'Tag:{key}={value.text}' if processing_values else f'Key:{key}'

    # prioritize wiki pages that match the user's language preferences
    for user_lang in user_langs:
        if user_lang not in wiki_locales:
            continue
        if user_lang == DEFAULT_LANGUAGE:
            url = f'https://wiki.openstreetmap.org/wiki/{page}'
        else:
            url = f'https://wiki.openstreetmap.org/wiki/{user_lang.title()}:{page}'
        return ValueFormat(value.text, 'url-safe', url)

    return value
