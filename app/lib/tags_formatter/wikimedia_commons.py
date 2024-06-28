import cython

from app.models.tag_format import TagFormat, TagFormatCollection


@cython.cfunc
def _is_wikimedia_entry(s: str) -> cython.char:
    return s.lower().startswith(('file:', 'category:'))


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_wikimedia_entry(value):
            success = True
            url = f'https://commons.wikimedia.org/wiki/{value}'
            new_styles.append(TagFormat(value, 'url-safe', url))
        else:
            new_styles.append(TagFormat(value))

    if success:
        tag.values = new_styles


def configure_wikimedia_commons_format(method_map: dict) -> None:
    method_map['wikimedia_commons'] = _format
