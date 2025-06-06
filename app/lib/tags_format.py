import re
from collections.abc import Callable
from pathlib import Path
from typing import overload

import cython
import orjson
import phonenumbers
from phonenumbers import (
    NumberParseException,
    PhoneNumberFormat,
    format_number,
    is_possible_number,
    is_valid_number,
)

from app.lib.rich_text import process_rich_text
from app.lib.wiki_pages import tags_format_osm_wiki
from app.models.tags_format import TagFormat, ValueFormat
from app.validators.email import validate_email

# TODO: 0.7 official reserved tag characters

# source: https://www.w3.org/TR/css-color-3/#svg-color
_W3C_COLORS = frozenset(orjson.loads(Path('config/w3c_colors.json').read_bytes()))

# make sure to match popular locale combinations, full spec is complex
# https://taginfo.openstreetmap.org/search?q=wikipedia%3A#keys
_WIKI_LANG_RE = re.compile(r'^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?$')
_WIKI_LANG_VALUE_RE = re.compile(
    r'^(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?):(?P<text>.+)$'
)


@overload
def tags_format(tags: None) -> None: ...
@overload
def tags_format(tags: dict[str, str]) -> dict[str, TagFormat]: ...
def tags_format(tags: dict[str, str] | None) -> dict[str, TagFormat] | None:
    """Format tags for displaying on the website (colors, urls, etc.)."""
    if tags is None:
        return None

    result = dict(sorted((key, TagFormat(key, value)) for key, value in tags.items()))
    result_values = list(result.values())

    for tag in result_values:
        # split a:b:c keys into ['a', 'b', 'c']
        key_parts = tag.key.text.split(':', maxsplit=5)
        values = tag.values
        for key_part in _SUPPORTED_KEYS.intersection(key_parts):
            for call in _FORMATTER_MAP[key_part]:
                values = call(key_parts, values)
        tag.values = values

    tags_format_osm_wiki(result_values)
    return result


@cython.cfunc
def _is_hex_color(s: str) -> cython.bint:
    return (
        (len(s) in {4, 7})
        and s[0] == '#'
        and all(
            '0' <= c <= '9'  #
            or 'A' <= c <= 'F'
            or 'a' <= c <= 'f'
            for c in s[1:]
        )
    )


@cython.cfunc
def _is_w3c_color(s: str) -> cython.bint:
    return s.lower() in _W3C_COLORS


@cython.cfunc
def _format_color(_: list[str], values: list[ValueFormat]) -> list[ValueFormat]:
    return [
        ValueFormat(value.text, 'color', value.text)
        if value.format is None
        and (_is_hex_color(value.text) or _is_w3c_color(value.text))
        else value
        for value in values
    ]


@cython.cfunc
def _format_comment(_: list[str], values: list[ValueFormat]) -> list[ValueFormat]:
    merged = ';'.join(value.text for value in values)
    rich_text = process_rich_text(merged, 'plain')
    return [ValueFormat(merged, 'html', rich_text)]


@cython.cfunc
def _is_email_string(s: str) -> cython.bint:
    try:
        validate_email(s)
    except ValueError:
        return False
    else:
        return True


@cython.cfunc
def _format_email(_: list[str], values: list[ValueFormat]) -> list[ValueFormat]:
    return [
        ValueFormat(value.text, 'email', f'mailto:{value.text}')
        if value.format is None and _is_email_string(value.text)
        else value
        for value in values
    ]


@cython.cfunc
def _get_phone_info(s: str):
    try:
        return phonenumbers.parse(s, None)
    except NumberParseException:
        return None


@cython.cfunc
def _format_phone(_: list[str], values: list[ValueFormat]) -> list[ValueFormat]:
    result: list[ValueFormat] = values.copy()
    num_format = PhoneNumberFormat.E164

    i: cython.Py_ssize_t
    for i, value in enumerate(values):
        if value.format is not None:
            continue
        info = _get_phone_info(value.text)
        if info is None or not is_possible_number(info) or not is_valid_number(info):
            continue
        result[i] = ValueFormat(
            value.text, 'phone', f'tel:{format_number(info, num_format)}'
        )

    return result


@cython.cfunc
def _is_url_string(s: str) -> cython.bint:
    return s.lower().startswith(('https://', 'http://'))


@cython.cfunc
def _format_url(_: list[str], values: list[ValueFormat]) -> list[ValueFormat]:
    return [
        ValueFormat(value.text, 'url', value.text)
        if value.format is None and _is_url_string(value.text)
        else value
        for value in values
    ]


@cython.cfunc
def _is_wiki_id(s: str) -> cython.bint:
    s_len: cython.Py_ssize_t = len(s)
    return (
        s_len >= 2
        and s[0] in 'Qq'
        and '1' <= s[1] <= '9'
        and all('0' <= s[i] <= '9' for i in range(2, s_len))
    )


@cython.cfunc
def _format_wikidata(_: list[str], values: list[ValueFormat]) -> list[ValueFormat]:
    return [
        ValueFormat(
            value.text, 'url-safe', f'https://www.wikidata.org/entity/{value.text}'
        )
        if value.format is None and _is_wiki_id(value.text)
        else value
        for value in values
    ]


@cython.cfunc
def _is_wikimedia_entry(s: str) -> cython.bint:
    return s.lower().startswith(('file:', 'category:'))


@cython.cfunc
def _format_wikimedia_commons(
    _: list[str], values: list[ValueFormat]
) -> list[ValueFormat]:
    return [
        ValueFormat(
            value.text, 'url-safe', f'https://commons.wikimedia.org/wiki/{value.text}'
        )
        if value.format is None and _is_wikimedia_entry(value.text)
        else value
        for value in values
    ]


@cython.cfunc
def _format_wikipedia(
    key_parts: list[str], values: list[ValueFormat]
) -> list[ValueFormat]:
    # always default to english
    lang = 'en'

    # check for key language override
    for key_part in key_parts:
        if _WIKI_LANG_RE.fullmatch(key_part) is not None:
            lang = key_part
            break

    return [_transform_wikipedia(lang, value) for value in values]


@cython.cfunc
def _transform_wikipedia(lang: str, value: ValueFormat):
    # skip already styled
    if value.format is not None:
        return value

    # check for value language override
    text = value.text
    if (match := _WIKI_LANG_VALUE_RE.fullmatch(text)) is not None:
        lang = match['lang']
        text = match['text']

    return ValueFormat(
        value.text, 'url-safe', f'https://{lang}.wikipedia.org/wiki/{text}'
    )


_FORMATTER_MAP: dict[
    str, list[Callable[[list[str], list[ValueFormat]], list[ValueFormat]]]
] = {
    'colour': [_format_color],
    'comment': [_format_comment],
    'email': [_format_email],
    'phone': [_format_phone],
    'fax': [_format_phone],
    'host': [_format_url],
    'website': [_format_url],
    'url': [_format_url],
    'source': [_format_url],
    'image': [_format_url],
    'wikidata': [_format_wikidata],
    'wikimedia_commons': [_format_wikimedia_commons],
    'wikipedia': [_format_url, _format_wikipedia],
}
_SUPPORTED_KEYS = frozenset(_FORMATTER_MAP)
