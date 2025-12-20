from pathlib import Path

import orjson

_DISCARDABLE_KEYS = frozenset(
    orjson.loads(Path('config/discardable_tags.json').read_bytes())
)


def remove_discardable_tags(
    tags: dict[str, str] | None,
    /,
    *,
    _DISCARDABLE_KEYS=_DISCARDABLE_KEYS,
):
    """
    Remove discardable tag keys in-place.
    Returns None when no tags remain.
    """
    if not tags:
        return None

    remove_keys: list[str] | None = None
    for key in tags:
        if key in _DISCARDABLE_KEYS:
            if remove_keys is None:
                remove_keys = [key]
            else:
                remove_keys.append(key)

    if remove_keys is None:
        return tags

    for key in remove_keys:
        del tags[key]

    return tags or None


def has_non_discardable_tags(
    tags: dict[str, str] | None,
    /,
    *,
    _DISCARDABLE_KEYS=_DISCARDABLE_KEYS,
) -> bool:
    """Return True if at least one non-discardable tag is present."""
    if not tags:
        return False

    for key in tags:
        if key not in _DISCARDABLE_KEYS:
            return True

    return False
