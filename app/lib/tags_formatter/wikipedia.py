import re

import cython

from app.models.tag_format import TagFormat, TagFormatCollection

# make sure to match popular locale combinations, full spec is complex
# https://taginfo.openstreetmap.org/search?q=wikipedia%3A#keys
_wiki_lang_re = re.compile(r'^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?$')
_wiki_lang_value_re = re.compile(r'^(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?):(?P<value>.+)$')


@cython.cfunc
def _is_url_string(s: str) -> cython.char:
    return s.lower().startswith(('https://', 'http://'))


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    # always default to english
    key_lang = 'en'

    # check for key language override
    for key_part in key_parts:
        if _wiki_lang_re.fullmatch(key_part) is not None:
            key_lang = key_part
            break

    success: cython.char = False
    new_styles = []

    for value in values:
        # return empty values without formatting
        if not value:
            new_styles.append(TagFormat(value))
            continue

        # return urls as-is
        if _is_url_string(value):
            success = True
            new_styles.append(TagFormat(value, 'url', value))
            continue

        lang = key_lang

        # check for value language override
        if (match := _wiki_lang_value_re.fullmatch(value)) is not None:
            lang = match['lang']
            value = match['value']

        reference, _, fragment = value.partition('#')

        url = f'https://{lang}.wikipedia.org/wiki/{reference}'

        if fragment:
            url += f'#{fragment}'

        success = True
        new_styles.append(TagFormat(value, 'url-safe', url))

    if success:
        tag.values = new_styles


def configure_wikipedia_format(method_map: dict) -> None:
    method_map['wikipedia'] = _format
