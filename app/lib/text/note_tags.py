from collections.abc import Mapping
from unicodedata import category

# Require a whitespace boundary so URL fragments, issue references embedded in
# words, and Markdown headings are not mistaken for note hashtags.
_HASHTAG_END = frozenset('#;,.:!?()[]{}<>')


def _valid_hashtag(tag: str):
    return (
        tag.startswith('#')
        and len(tag) > 1
        and all(
            char.isalnum() or char in '_-' or category(char).startswith('M')
            for char in tag[1:]
        )
    )


def valid_note_hashtags(value: str):
    return not value or all(_valid_hashtag(tag) for tag in value.split(';'))


def extract_note_hashtags(text: str):
    """Extract standalone hashtags for API 0.6 imports and legacy migrations."""
    hashtags: dict[str, None] = {}
    parts: list[str] = []
    offset = 0
    for start, char in enumerate(text):
        if char != '#' or (start and not text[start - 1].isspace()):
            continue
        end = start + 1
        while (
            end < len(text)
            and not text[end].isspace()
            and text[end] not in _HASHTAG_END
        ):
            end += 1
        if end < len(text) and text[end] == '#':
            continue
        tag = text[start:end]
        if _valid_hashtag(tag):
            hashtags[tag] = None
            parts.append(text[offset:start])
            offset = end
    if not hashtags:
        return text, None
    parts.append(text[offset:])
    return ''.join(parts).strip(), {'hashtags': ';'.join(hashtags)}


def append_note_hashtags(text: str, tags: Mapping[str, str] | None):
    """Expose a comment's own tag snapshot to legacy text-only consumers."""
    hashtags = (tags or {}).get('hashtags', '').replace(';', ' ')
    if not hashtags:
        return text
    return f'{text}\n{hashtags}' if text else hashtags
