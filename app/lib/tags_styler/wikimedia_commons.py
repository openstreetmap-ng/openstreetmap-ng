import cython

from app.lib.translation import primary_translation_language
from app.models.tag_style import TagStyle, TagStyleCollection


@cython.cfunc
def _is_wikimedia_entry(s: str) -> cython.char:
    return s.lower().startswith(('file:', 'category:'))


@cython.cfunc
def _format_wikimedia_commons(tag: TagStyleCollection, key_parts: list[str], values: list[str]) -> None:
    user_lang = primary_translation_language()
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_wikimedia_entry(value):
            success = True
            url = f'https://commons.wikimedia.org/wiki/{value}?uselang={user_lang}'
            new_styles.append(TagStyle(value, 'url-safe', url))
        else:
            new_styles.append(TagStyle(value))

    if success:
        tag.values = new_styles


def configure_wikimedia_commons_style(method_map: dict) -> None:
    method_map['wikimedia_commons'] = _format_wikimedia_commons
