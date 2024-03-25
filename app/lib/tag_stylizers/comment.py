import cython

from app.lib.rich_text import process_rich_text
from app.models.tag_style import TagStyle, TagStyleCollection
from app.models.text_format import TextFormat


@cython.cfunc
def _format_comment(tag: TagStyleCollection, key_parts: list[str], values: list[str]) -> None:
    value = ';'.join(values)
    rich_value = process_rich_text(value, TextFormat.plain)

    if value != rich_value:
        tag.values = (TagStyle(value, 'html', rich_value),)


def configure_comment_style(method_map: dict) -> None:
    method_map['comment'] = _format_comment
