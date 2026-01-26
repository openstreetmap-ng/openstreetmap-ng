import unicodedata
from urllib.parse import unquote_plus

from pydantic import BeforeValidator


def unicode_unquote_normalize(text: str):
    """Unquote URL-encoded text and normalize to NFC form."""
    return unicodedata.normalize('NFC', unquote_plus(text))


UnicodeValidator = BeforeValidator(unicode_unquote_normalize)
