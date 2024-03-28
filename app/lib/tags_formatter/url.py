import cython

from app.models.tag_format import TagFormat, TagFormatCollection


@cython.cfunc
def _is_url_string(s: str) -> cython.char:
    return s.lower().startswith(('https://', 'http://'))


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_url_string(value):
            success = True
            new_styles.append(TagFormat(value, 'url', value))
        else:
            new_styles.append(TagFormat(value))

    if success:
        tag.values = new_styles


def configure_url_format(method_map: dict) -> None:
    for key in (
        'host',
        'url',
        'website',
        'source',
        'image',
    ):
        method_map[key] = _format
