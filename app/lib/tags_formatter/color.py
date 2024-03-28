import json
import pathlib

import cython

from app.config import CONFIG_DIR
from app.models.tag_format import TagFormat, TagFormatCollection

# source: https://www.w3.org/TR/css-color-3/#svg-color
_w3c_colors = frozenset(json.loads(pathlib.Path(CONFIG_DIR / 'w3c_colors.json').read_bytes()))


@cython.cfunc
def _is_hex_color(s: str) -> cython.char:
    s_len: cython.int = len(s)
    if s_len != 4 and s_len != 7:
        return False

    if s[0] != '#':
        return False

    i: cython.int
    for i in range(1, s_len):
        c = s[i]
        if not (('0' <= c <= '9') or ('A' <= c <= 'F') or ('a' <= c <= 'f')):
            return False

    return True


@cython.cfunc
def _is_w3c_color(s: str) -> cython.char:
    return s.lower() in _w3c_colors


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_hex_color(value) or _is_w3c_color(value):
            success = True
            new_styles.append(TagFormat(value, 'color', value))
        else:
            new_styles.append(TagFormat(value))

    if success:
        tag.values = new_styles


def configure_color_format(method_map: dict) -> None:
    method_map['colour'] = _format
