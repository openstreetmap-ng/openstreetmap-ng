import cython

from app.models.tag_style import TagStyle, TagStyleCollection


@cython.cfunc
def _is_url_string(s: str) -> cython.char:
    return s.lower().startswith(('https://', 'http://'))


@cython.cfunc
def _format_url(tag: TagStyleCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_url_string(value):
            success = True
            new_styles.append(TagStyle(value, 'url', value))
        else:
            new_styles.append(TagStyle(value))

    if success:
        tag.values = new_styles


def configure_url_style(method_map: dict) -> None:
    for key in (
        'host',
        'url',
        'website',
        'source',
        'image',
    ):
        method_map[key] = _format_url
