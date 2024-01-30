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

# read property once for performance
_fmt_default = TagFormat.default
_fmt_color = TagFormat.color
_fmt_email = TagFormat.email
_fmt_phone = TagFormat.phone
_fmt_url = TagFormat.url


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

    # split a:b:c keys into ['a', 'b', 'c']
    key_parts = key.split(':', maxsplit=max_key_parts)

    # skip unexpectedly long sequences
    if len(key_parts) > max_key_parts:
        return (TagFormatTuple(_fmt_default, value, value),)

    # iterate over each supported key format
    for key_format_key in _key_format_map_keys.intersection(key_parts):
        # split a;b;c values into ['a', 'b', 'c']
        values = value.split(';', maxsplit=max_values)

        # skip unexpectedly long sequences
        if len(values) > max_values:
            return (TagFormatTuple(_fmt_default, value, value),)

        return _key_format_map[key_format_key](key_parts, values)

    return (TagFormatTuple(_fmt_default, value, value),)


@cython.cfunc
def _is_hex_color(s: str) -> cython.char:
    s_len: cython.int = len(s)
    if s_len != 4 and s_len != 7:
        return False

    if s[0] != '#':
        return False

    i: cython.int
    for i in range(1, s_len + 1):
        c = s[i]
        if not (('0' <= c <= '9') or ('A' <= c <= 'F') or ('a' <= c <= 'f')):
            return False

    return False


@cython.cfunc
def _is_w3c_color(s: str) -> cython.char:
    return s.lower() in _w3c_colors


@cython.cfunc
def _format_color(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    return tuple(
        TagFormatTuple(_fmt_color, s, s)
        if (_is_hex_color(s) or _is_w3c_color(s))
        else TagFormatTuple(_fmt_default, s, s)
        for s in values
    )


@cython.cfunc
def _is_email_string(s: str) -> cython.char:
    try:
        validate_email(s)
        return True
    except ValueError:
        return False


@cython.cfunc
def _format_email(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    return tuple(
        TagFormatTuple(_fmt_email, s, f'mailto:{s}')
        if _is_email_string(
            s,
        )
        else TagFormatTuple(_fmt_default, s, s)
        for s in values
    )


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

    return tuple(
        TagFormatTuple(_fmt_phone, s, f'tel:{format_number(phone_info, PhoneNumberFormat.E164)}')
        if (phone_info := get_phone_info(s)) is not None
        else TagFormatTuple(_fmt_default, s, s)
        for s in values
    )


@cython.cfunc
def _is_url_string(s: str) -> cython.char:
    return s.lower().startswith(('https://', 'http://'))


@cython.cfunc
def _format_url(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    return tuple(
        TagFormatTuple(_fmt_url, s, s)
        if _is_url_string(
            s,
        )
        else TagFormatTuple(_fmt_default, s, s)
        for s in values
    )


@cython.cfunc
def _format_wikipedia(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    # always default to english
    key_lang = 'en'
    user_lang = primary_translation_language()

    # check for key language override
    for key_part in key_parts:
        if _wiki_lang_re.fullmatch(key_part) is not None:
            key_lang = key_part
            break

    def format_value(s: str) -> TagFormatTuple:
        # return empty values without formatting
        if not s:
            return TagFormatTuple(_fmt_default, s, s)

        # return urls as-is
        if _is_url_string(s):
            return TagFormatTuple(_fmt_url, s, s)

        lang = key_lang

        # check for value language override
        if (match := _wiki_lang_value_re.fullmatch(s)) is not None:
            lang = match['lang']
            s = match['value']

        reference, _, fragment = s.partition('#')

        url = f'https://{lang}.wikipedia.org/wiki/{reference}?uselang={user_lang}'

        if fragment:
            url += f'#{fragment}'

        return TagFormatTuple(_fmt_url, s, url)

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_wiki_id(s: str) -> cython.char:
    s_len: cython.int = len(s)
    if s_len < 2:
        return False

    s_0 = s[0]
    if s_0 != 'Q' and s_0 != 'q':
        return False

    if not ('1' <= s[1] <= '9'):
        return False

    i: cython.int
    for i in range(2, s_len + 1):  # noqa: SIM110
        if not ('0' <= s[i] <= '9'):
            return False

    return True


@cython.cfunc
def _format_wikidata(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    user_lang = primary_translation_language()

    return tuple(
        TagFormatTuple(_fmt_url, s, f'https://www.wikidata.org/entity/{s}?uselang={user_lang}')
        if _is_wiki_id(s)
        else TagFormatTuple(_fmt_default, s, s)
        for s in values
    )


@cython.cfunc
def _is_wikimedia_entry(s: str) -> cython.char:
    return s.lower().startswith(('file:', 'category:'))


@cython.cfunc
def _format_wikimedia_commons(key_parts: Sequence[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    user_lang = primary_translation_language()

    return tuple(
        TagFormatTuple(_fmt_url, s, f'https://commons.wikimedia.org/wiki/{s}?uselang={user_lang}')
        if _is_wikimedia_entry(s)
        else TagFormatTuple(_fmt_default, s, s)
        for s in values
    )


# map tag keys to formatting functions
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
