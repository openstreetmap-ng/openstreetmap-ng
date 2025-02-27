from collections.abc import Iterable

import cython

from app.validators.tags import TagsValidator


class Tag06Mixin:
    @staticmethod
    def decode_tags_and_validate(tags: Iterable[dict]) -> dict[str, str]:
        """
        >>> decode_tags_and_validate([
        ...     {'@k': 'a', '@v': '1'},
        ...     {'@k': 'b', '@v': '2'},
        ... ])
        {'a': '1', 'b': '2'}
        """
        return TagsValidator.validate_python(_decode_tags_unsafe(tags))


@cython.cfunc
def _decode_tags_unsafe(tags: Iterable[dict]) -> dict:
    """
    This method does not validate the input data.

    >>> _decode_tags_unsafe([
    ...     {'@k': 'a', '@v': '1'},
    ...     {'@k': 'b', '@v': '2'},
    ... ])
    {'a': '1', 'b': '2'}
    """
    items = [(tag['@k'], tag['@v']) for tag in tags]
    result = dict(items)
    if len(items) != len(result):
        raise ValueError('Duplicate tag keys')
    return result
