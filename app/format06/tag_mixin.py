from collections.abc import Sequence

import cython

from app.validators.tags import TagsValidating


class Tag06Mixin:
    @staticmethod
    def decode_tags_and_validate(tags: Sequence[dict]) -> dict[str, str]:
        """
        >>> decode_tags_and_validate([
        ...     {'@k': 'a', '@v': '1'},
        ...     {'@k': 'b', '@v': '2'},
        ... ])
        {'a': '1', 'b': '2'}
        """
        return TagsValidating(tags=_decode_tags_unsafe(tags)).tags


@cython.cfunc
def _decode_tags_unsafe(tags: Sequence[dict]) -> dict:
    """
    This method does not validate the input data.

    >>> _decode_tags_unsafe([
    ...     {'@k': 'a', '@v': '1'},
    ...     {'@k': 'b', '@v': '2'},
    ... ])
    {'a': '1', 'b': '2'}
    """
    items = tuple((tag['@k'], tag['@v']) for tag in tags)
    result = dict(items)

    if len(items) != len(result):
        raise ValueError('Duplicate tag keys')

    return result
