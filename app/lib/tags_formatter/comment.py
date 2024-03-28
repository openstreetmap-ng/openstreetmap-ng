from app.lib.rich_text import process_rich_text
from app.models.tag_format import TagFormat, TagFormatCollection
from app.models.text_format import TextFormat


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    value = ';'.join(values)
    rich_value = process_rich_text(value, TextFormat.plain)

    if value != rich_value:
        tag.values = (TagFormat(value, 'html', rich_value),)


def configure_comment_format(method_map: dict) -> None:
    method_map['comment'] = _format
