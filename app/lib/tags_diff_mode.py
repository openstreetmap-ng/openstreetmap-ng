from copy import copy

from app.lib.tags_format import tags_format
from app.models.db.element import Element
from app.models.tags_format import TagFormat


def tags_diff_mode(previous_element: Element | None, elements_data: tuple[dict, ...]) -> None:
    """
    Update tags data to include necessary tags diff mode information.
    """
    added_tags: list[tuple[str, TagFormat]] = []
    modified_tags: list[tuple[str, TagFormat]] = []
    unchanged_tags: list[tuple[str, TagFormat]] = []
    previous_tags: dict[str, TagFormat] = tags_format(previous_element.tags) if (previous_element is not None) else {}

    for current in reversed(elements_data):
        current_element: Element = current['element']
        current_tags: dict[str, TagFormat] = current['tags_map']
        if current_element.version == 1:
            previous_tags = current_tags
            continue

        for item in current_tags.items():
            key, tag = item
            previous_tag = previous_tags.get(key)
            if previous_tag is None:
                tag.status = 'added'
                added_tags.append(item)
            elif previous_tag.values != tag.values:
                tag.status = 'modified'
                tag.previous = previous_tag.values
                modified_tags.append(item)
            else:
                unchanged_tags.append(item)

        new_tags: dict[str, TagFormat] = dict(added_tags)
        new_tags.update(modified_tags)
        new_tags.update(unchanged_tags)
        added_tags.clear()
        modified_tags.clear()
        unchanged_tags.clear()

        for key, tag in previous_tags.items():
            if key not in current_tags:
                deleted_tag = copy(tag)
                deleted_tag.status = 'deleted'
                deleted_tag.previous = None
                new_tags[key] = deleted_tag

        previous_tags = current_tags
        current['tags_map'] = new_tags
