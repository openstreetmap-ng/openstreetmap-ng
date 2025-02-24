import unicodedata

from pydantic import BeforeValidator


def unicode_normalize(text: str) -> str:
    """Normalize a string to NFC form."""
    return unicodedata.normalize('NFC', text)


UnicodeValidator = BeforeValidator(unicode_normalize)
