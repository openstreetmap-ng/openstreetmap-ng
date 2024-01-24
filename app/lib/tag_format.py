import pathlib
import re
from collections.abc import Sequence
from typing import NamedTuple

import cython
import orjson
import phonenumbers
from phonenumbers import (
    NumberParseException,
    PhoneNumber,
    PhoneNumberFormat,
    format_number,
    is_possible_number,
    is_valid_number,
)

from app.config import CONFIG_DIR
from app.lib.email import validate_email
from app.lib.translation import primary_translation_language
from app.models.tag_format import TagFormat


class TagFormatTuple(NamedTuple):
    format: TagFormat  # noqa: A003
    value: str
    data: str


# TODO: 0.7 official reserved tag characters

# make sure to match popular locale combinations, full spec is complex
# https://taginfo.openstreetmap.org/search?q=wikipedia%3A#keys
_wiki_lang_re = re.compile(r'^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?$')
_wiki_lang_value_re = re.compile(r'^(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?):(?P<value>.+)$')

# source: https://www.w3.org/TR/css-color-3/#svg-color
_w3c_colors = frozenset(orjson.loads(pathlib.Path(CONFIG_DIR / 'w3c_colors.json').read_bytes()))


def tag_format(key: str, value: str) -> Sequence[TagFormatTuple]:
    """
    Return a sequence of tag formats for a key/value pair.

    Returns None if the format is not recognized.

    >>> tag_format('colour', '#ff0000;invalid;aliceblue')
    [
        (TagFormat.color, '#ff0000'),
        (TagFormat.default, 'invalid'),
        (TagFormat.color, 'aliceblue')
    ]

    >>> tag_format('amenity', 'restaurant;cafe')
    [(TagFormat.default, 'restaurant;cafe')]
    """

    # small optimization
    if not value:
        return ()

    max_key_parts: cython.int = 5
    max_values: cython.int = 8
    default_result = (TagFormatTuple(TagFormat.default, value, value),)

    # split a:b:c keys into ['a', 'b', 'c']
    key_parts = key.split(':', maxsplit=max_key_parts)

    # skip unexpectedly long sequences
    if len(key_parts) > max_key_parts:
        return default_result

    # iterate over each supported key format
    for key_format_key in _key_format_map_keys.intersection(key_parts):
        # split a;b;c values into ['a', 'b', 'c']
        values = value.split(';', maxsplit=max_values)

        # skip unexpectedly long sequences
        if len(values) > max_values:
            return default_result

        return _key_format_map[key_format_key](key_parts, values)

    return default_result


@cython.cfunc
def _is_color_string(s: str) -> cython.char:
    # hex or w3c color name
    return (
        len(s) in (4, 7)
        and s[0] == '#'
        and all(('0' <= c <= '9') or ('A' <= c <= 'F') or ('a' <= c <= 'f') for c in s[1:])
    ) or s.lower() in _w3c_colors


@cython.cfunc
def _format_color(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def format_value(s: str) -> TagFormatTuple:
        return TagFormatTuple(TagFormat.color, s, s) if _is_color_string(s) else TagFormatTuple(TagFormat.default, s, s)

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_email_string(s: str) -> cython.char:
    try:
        validate_email(s)
        return True
    except ValueError:
        return False


@cython.cfunc
def _format_email(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def format_value(s: str) -> TagFormatTuple:
        return (
            TagFormatTuple(TagFormat.email, s, f'mailto:{s}')
            if _is_email_string(s)
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _format_phone(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def get_phone_info(s: str) -> PhoneNumber | None:
        try:
            info = phonenumbers.parse(s, None)
        except NumberParseException:
            return None

        if not is_possible_number(info):
            return None
        if not is_valid_number(info):
            return None

        return info

    def format_value(s: str) -> TagFormatTuple:
        phone_info = get_phone_info(s)
        return (
            TagFormatTuple(TagFormat.phone, s, f'tel:{format_number(phone_info, PhoneNumberFormat.E164)}')
            if phone_info
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_url_string(s: str) -> cython.char:
    return s.lower().startswith(('https://', 'http://'))


@cython.cfunc
def _format_url(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def format_value(s: str) -> TagFormatTuple:
        return TagFormatTuple(TagFormat.url, s, s) if _is_url_string(s) else TagFormatTuple(TagFormat.default, s, s)

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _format_wikipedia(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    # always default to english
    key_lang = 'en'
    user_lang = primary_translation_language()

    # check for key language override
    for key_part in key_parts:
        if _wiki_lang_re.fullmatch(key_part):
            key_lang = key_part
            break

    def format_value(s: str) -> TagFormatTuple:
        # return empty values without formatting
        if not s:
            return TagFormatTuple(TagFormat.default, s, s)

        # return urls as-is
        if _is_url_string(s):
            return TagFormatTuple(TagFormat.url, s, s)

        lang = key_lang

        # check for value language override
        if match := _wiki_lang_value_re.fullmatch(s):
            lang = match['lang']
            s = match['value']

        reference, _, fragment = s.partition('#')

        url = f'https://{lang}.wikipedia.org/wiki/{reference}?uselang={user_lang}'

        if fragment:
            url += f'#{fragment}'

        return TagFormatTuple(TagFormat.url, s, url)

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_wiki_id(s: str) -> cython.char:
    return len(s) >= 2 and (s[0] == 'Q' or s[0] == 'q') and ('1' <= s[1] <= '9') and all('0' <= c <= '9' for c in s[2:])


@cython.cfunc
def _format_wikidata(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    user_lang = primary_translation_language()

    def format_value(s: str) -> TagFormatTuple:
        return (
            TagFormatTuple(TagFormat.url, s, f'https://www.wikidata.org/entity/{s}?uselang={user_lang}')
            if _is_wiki_id(s)
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_wikimedia_entry(s: str) -> cython.char:
    return s.lower().startswith(('file:', 'category:'))


@cython.cfunc
def _format_wikimedia_commons(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    user_lang = primary_translation_language()

    def format_value(s: str) -> TagFormatTuple:
        return (
            TagFormatTuple(TagFormat.url, s, f'https://commons.wikimedia.org/wiki/{s}?uselang={user_lang}')
            if _is_wikimedia_entry(s)
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


_key_format_map = {
    'colour': _format_color,
    'email': _format_email,
    'phone': _format_phone,
    'fax': _format_phone,
    'url': _format_url,
    'website': _format_url,
    'wikipedia': _format_wikipedia,
    'wikidata': _format_wikidata,
    'wikimedia_commons': _format_wikimedia_commons,
}

_key_format_map_keys = frozenset(_key_format_map.keys())
