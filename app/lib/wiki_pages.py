from pathlib import Path

import cython
import orjson

from app.lib.locale import DEFAULT_LOCALE, normalize_locale
from app.lib.translation import translation_locales
from app.models.tags_format import TagFormat, ValueFormat
from app.models.types import LocaleCode

# TODO: perhaps support glob matches: Key:*:lanes


@cython.cfunc
def _get_wiki_pages() -> dict[tuple[str, str], frozenset[str | None]]:
    data = orjson.loads(Path('config/wiki_pages.json').read_bytes())
    return {
        (key, value): frozenset(
            normalize_locale(locale) if locale else DEFAULT_LOCALE
            for locale in locales  #
        )
        for key, value_locales in data.items()
        for value, locales in value_locales.items()
    }


# mapping of tags to a set of locales that have a wiki page
_WIKI_PAGES = _get_wiki_pages()


def tags_format_osm_wiki(tags: list[TagFormat]) -> None:
    """Format tags with supported wiki links."""
    locales = translation_locales()
    for tag in tags:
        key = tag.key.text
        tag.key = _transform(
            key=key,
            value=tag.key,
            processing_values=False,
            locales=locales,
        )
        tag.values = [
            _transform(
                key=key,
                value=value,
                processing_values=True,
                locales=locales,
            )
            for value in tag.values
        ]


@cython.cfunc
def _transform(
    key: str,
    value: ValueFormat,
    *,
    processing_values: cython.bint,
    locales: tuple[LocaleCode, ...],
):
    # skip already styled
    if value.format is not None:
        return value

    wiki_locales = _WIKI_PAGES.get((key, value.text) if processing_values else (key, '*'))
    if wiki_locales is None:
        return value

    page = f'Tag:{key}={value.text}' if processing_values else f'Key:{key}'

    # prioritize wiki pages that match the user's language preferences
    for locale in locales:
        if locale in wiki_locales:
            url = (
                f'https://wiki.openstreetmap.org/wiki/{page}'
                if locale == DEFAULT_LOCALE
                else f'https://wiki.openstreetmap.org/wiki/{locale.title()}:{page}'
            )
            return ValueFormat(value.text, 'url-safe', url)

    return value
