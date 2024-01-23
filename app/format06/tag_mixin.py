from collections.abc import Sequence

from app.lib.format_style_context import format_is_json
from app.models.validating.tags import TagsValidating


class Tag06Mixin:
    @staticmethod
    def encode_tags(tags: dict) -> Sequence[dict] | dict:
        """
        >>> encode_tags({'a': '1', 'b': '2'})
        [{'@k': 'a', '@v': '1'}, {'@k': 'b', '@v': '2'}]
        """

        if format_is_json():
            return tags
        else:
            return tuple({'@k': k, '@v': v} for k, v in tags.items())

    @staticmethod
    def decode_tags_unsafe(tags: Sequence[dict]) -> dict:
        """
        This method does not validate the input data.

        >>> decode_tags_unsafe([
        ...     {'@k': 'a', '@v': '1'},
        ...     {'@k': 'b', '@v': '2'},
        ... ])
        {'a': '1', 'b': '2'}
        """

        items = tuple((tag['@k'], tag['@v']) for tag in tags)
        result = dict(items)

        if len(items) != len(result):
            raise ValueError('Duplicate tags keys')

        return result

    @staticmethod
    def decode_tags_and_validate(tags: Sequence[dict]) -> dict[str, str]:
        """
        >>> decode_tags_and_validate([
        ...     {'@k': 'a', '@v': '1'},
        ...     {'@k': 'b', '@v': '2'},
        ... ])
        {'a': '1', 'b': '2'}
        """

        return TagsValidating(tags=Tag06Mixin.decode_tags_unsafe(tags)).tags
