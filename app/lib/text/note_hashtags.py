from unicodedata import category


def extract_note_hashtags(text: str) -> tuple[str, dict[str, str] | None]:
    """Separate whitespace-delimited hashtags from a legacy plain-text comment.

    Preserve URL fragments and unsupported tokens as text. If the complete value
    exceeds the tag-value limit, leave the comment untouched rather than silently
    losing hashtags. None means this comment does not change the note's tags.
    """
    spans: list[tuple[int, int]] = []
    hashtags: dict[str, None] = {}
    for start, char in enumerate(text):
        if char != '#' or (start and not text[start - 1].isspace()):
            continue
        end = start + 1
        while end < len(text):
            char = text[end]
            if char not in '_-' and category(char)[0] not in 'LNM':
                break
            end += 1
        # A hashtag must contain a letter or number, not only marks/punctuation.
        token = text[start:end]
        if not any(category(char)[0] in 'LN' for char in token[1:]):
            continue
        hashtags[token] = None
        spans.append((start, end))

    if not hashtags:
        return text, None

    value = ';'.join(hashtags)
    if len(value) > 255:
        return text, None

    chunks: list[str] = []
    cursor = 0
    for start, end in spans:
        chunks.append(text[cursor:start])
        cursor = end
    chunks.append(text[cursor:])
    return ''.join(chunks).strip(), {'hashtags': value}


def append_note_hashtags(text: str, tags: dict[str, str] | None) -> str:
    """Restore a comment's own hashtag snapshot for legacy text consumers."""
    value = tags.get('hashtags') if tags else None
    if not value:
        return text
    hashtags = ' '.join(value.split(';'))
    return f'{text}\n{hashtags}' if text else hashtags
