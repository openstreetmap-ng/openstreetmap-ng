import re
from collections.abc import Sequence
from typing import NamedTuple

import cython
import phonenumbers
from phonenumbers import (
    NumberParseException,
    PhoneNumber,
    PhoneNumberFormat,
    format_number,
    is_possible_number,
    is_valid_number,
)

from src.lib.email import Email
from src.lib.translation import translation_languages
from src.models.tag_format import TagFormat

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')
else:
    print(f'{__name__}: 🐌 not compiled')


class TagFormatTuple(NamedTuple):
    format: TagFormat  # noqa: A003
    value: str
    data: str


# TODO: 0.7 official reserved characters


# make sure to match popular locale combinations, full spec is complex
# https://taginfo.openstreetmap.org/search?q=wikipedia%3A#keys
_WIKI_LANG_RE = re.compile(r'^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?$')
_WIKI_LANG_VALUE_RE = re.compile(r'^(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?):(?P<value>.+)$')


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

    key_parts = _get_key_parts(key, maxsplit=max_key_parts)

    # skip unexpectedly long sequences
    if len(key_parts) > max_key_parts:
        return default_result

    key_parts = frozenset(key_parts)

    for check_key, format_values in (
        (_is_color_key, _format_color),
        (_is_email_key, _format_email),
        (_is_phone_key, _format_phone),
        (_is_url_key, _format_url),
        (_is_wikipedia_key, _format_wikipedia),
        (_is_wikidata_key, _format_wikidata),
        (_is_wikimedia_commons_key, _format_wikimedia_commons),
    ):
        if not check_key(key_parts):
            continue

        values = _get_values(value, maxsplit=max_values)

        # skip unexpectedly long sequences
        if len(values) > max_values:
            return default_result

        return format_values(key_parts, values)

    return default_result


@cython.cfunc
def _get_key_parts(key: str, *, maxsplit: cython.int) -> list[str]:
    """
    Split a key into parts using ':' as a separator.
    """

    return key.split(':', maxsplit=maxsplit)


@cython.cfunc
def _get_values(value: str, *, maxsplit: cython.int) -> list[str]:
    """
    Split a value into parts using ';' as a separator.
    """

    return value.split(';', maxsplit=maxsplit)


@cython.cfunc
def _is_color_key(key_parts: frozenset[str]) -> cython.char:
    return 'colour' in key_parts


@cython.cfunc
def _format_color(_: frozenset[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def is_hex(s: str) -> cython.char:
        return (
            len(s) in (4, 7)
            and s[0] == '#'
            and all(('0' <= c <= '9') or ('A' <= c <= 'F') or ('a' <= c <= 'f') for c in s[1:])
        )

    def is_w3c_color(s: str) -> cython.char:
        return s.lower() in _W3C_COLORS

    def format_value(s: str) -> TagFormatTuple:
        return (
            TagFormatTuple(TagFormat.color, s, s)
            if (is_hex(s) or is_w3c_color(s))
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_email_key(key_parts: frozenset[str]) -> cython.char:
    return 'email' in key_parts


@cython.cfunc
def _format_email(_: frozenset[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def is_email(s: str) -> cython.char:
        try:
            Email.validate(s)
            return True
        except ValueError:
            return False

    def format_value(s: str) -> TagFormatTuple:
        return (
            TagFormatTuple(TagFormat.email, s, f'mailto:{s}')
            if is_email(s)
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_phone_key(key_parts: frozenset[str]) -> cython.char:
    return key_parts.intersection(('phone', 'fax'))


@cython.cfunc
def _format_phone(_: frozenset[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
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
def _is_url_key(key_parts: frozenset[str]) -> cython.char:
    return key_parts.intersection(('url', 'website'))


@cython.cfunc
def _format_url(_: frozenset[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def is_url(s: str) -> cython.char:
        return s.startswith(('https://', 'http://'))

    def format_value(s: str) -> TagFormatTuple:
        return TagFormatTuple(TagFormat.url, s, s) if is_url(s) else TagFormatTuple(TagFormat.default, s, s)

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_wikipedia_key(key_parts: frozenset[str]) -> cython.char:
    return 'wikipedia' in key_parts


@cython.cfunc
def _format_wikipedia(key_parts: frozenset[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    # always default to english
    key_lang = 'en'
    user_lang = translation_languages()[0]

    # check for key language override
    for key_part in key_parts:
        if _WIKI_LANG_RE.fullmatch(key_part):
            key_lang = key_part
            break

    def is_url(s: str) -> cython.char:
        return s.startswith(('https://', 'http://'))

    def format_value(s: str) -> TagFormatTuple:
        # return empty values without formatting
        if not s:
            return TagFormatTuple(TagFormat.default, s, s)

        # return urls as-is
        if is_url(s):
            return TagFormatTuple(TagFormat.url, s, s)

        lang = key_lang

        # check for value language override
        if match := _WIKI_LANG_VALUE_RE.fullmatch(s):
            lang = match['lang']
            s = match['value']

        reference, _, fragment = s.partition('#')

        url = f'https://{lang}.wikipedia.org/wiki/{reference}?uselang={user_lang}'

        if fragment:
            url += f'#{fragment}'

        return TagFormatTuple(TagFormat.url, s, url)

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_wikidata_key(key_parts: frozenset[str]) -> cython.char:
    return 'wikidata' in key_parts


@cython.cfunc
def _format_wikidata(_: frozenset[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def is_wiki_id(s: str) -> cython.char:
        return len(s) >= 2 and s[0] == 'Q' and ('1' <= s[1] <= '9') and all('0' <= c <= '9' for c in s[2:])

    def format_value(s: str) -> TagFormatTuple:
        return (
            TagFormatTuple(
                TagFormat.url, s, f'https://www.wikidata.org/entity/{s}?uselang={translation_languages()[0]}'
            )
            if is_wiki_id(s)
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


@cython.cfunc
def _is_wikimedia_commons_key(key_parts: frozenset[str]) -> cython.char:
    return 'wikimedia_commons' in key_parts


@cython.cfunc
def _format_wikimedia_commons(_: frozenset[str], values: list[str]) -> tuple[TagFormatTuple, ...]:
    def is_entry(s: str) -> cython.char:
        # intentionally don't support lowercase to promote consistency
        return s.startswith(('File:', 'Category:'))

    def format_value(s: str) -> TagFormatTuple:
        return (
            TagFormatTuple(
                TagFormat.url, s, f'https://commons.wikimedia.org/wiki/{s}?uselang={translation_languages()[0]}'
            )
            if is_entry(s)
            else TagFormatTuple(TagFormat.default, s, s)
        )

    return tuple(format_value(s) for s in values)


# source: https://www.w3.org/TR/css-color-3/#svg-color
_W3C_COLORS = frozenset(
    (
        'aliceblue',
        'antiquewhite',
        'aqua',
        'aquamarine',
        'azure',
        'beige',
        'bisque',
        'black',
        'blanchedalmond',
        'blue',
        'blueviolet',
        'brown',
        'burlywood',
        'cadetblue',
        'chartreuse',
        'chocolate',
        'coral',
        'cornflowerblue',
        'cornsilk',
        'crimson',
        'cyan',
        'darkblue',
        'darkcyan',
        'darkgoldenrod',
        'darkgray',
        'darkgrey',
        'darkgreen',
        'darkkhaki',
        'darkmagenta',
        'darkolivegreen',
        'darkorange',
        'darkorchid',
        'darkred',
        'darksalmon',
        'darkseagreen',
        'darkslateblue',
        'darkslategray',
        'darkslategrey',
        'darkturquoise',
        'darkviolet',
        'deeppink',
        'deepskyblue',
        'dimgray',
        'dimgrey',
        'dodgerblue',
        'firebrick',
        'floralwhite',
        'forestgreen',
        'fuchsia',
        'gainsboro',
        'ghostwhite',
        'gold',
        'goldenrod',
        'gray',
        'grey',
        'green',
        'greenyellow',
        'honeydew',
        'hotpink',
        'indianred',
        'indigo',
        'ivory',
        'khaki',
        'lavender',
        'lavenderblush',
        'lawngreen',
        'lemonchiffon',
        'lightblue',
        'lightcoral',
        'lightcyan',
        'lightgoldenrodyellow',
        'lightgray',
        'lightgrey',
        'lightgreen',
        'lightpink',
        'lightsalmon',
        'lightseagreen',
        'lightskyblue',
        'lightslategray',
        'lightslategrey',
        'lightsteelblue',
        'lightyellow',
        'lime',
        'limegreen',
        'linen',
        'magenta',
        'maroon',
        'mediumaquamarine',
        'mediumblue',
        'mediumorchid',
        'mediumpurple',
        'mediumseagreen',
        'mediumslateblue',
        'mediumspringgreen',
        'mediumturquoise',
        'mediumvioletred',
        'midnightblue',
        'mintcream',
        'mistyrose',
        'moccasin',
        'navajowhite',
        'navy',
        'oldlace',
        'olive',
        'olivedrab',
        'orange',
        'orangered',
        'orchid',
        'palegoldenrod',
        'palegreen',
        'paleturquoise',
        'palevioletred',
        'papayawhip',
        'peachpuff',
        'peru',
        'pink',
        'plum',
        'powderblue',
        'purple',
        'red',
        'rosybrown',
        'royalblue',
        'saddlebrown',
        'salmon',
        'sandybrown',
        'seagreen',
        'seashell',
        'sienna',
        'silver',
        'skyblue',
        'slateblue',
        'slategray',
        'slategrey',
        'snow',
        'springgreen',
        'steelblue',
        'tan',
        'teal',
        'thistle',
        'tomato',
        'turquoise',
        'violet',
        'wheat',
        'white',
        'whitesmoke',
        'yellow',
        'yellowgreen',
    )
)
