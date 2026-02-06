import unicodedata
from urllib.parse import unquote_plus

from pydantic import BeforeValidator

from app.models.types import DisplayName


def unicode_unquote_normalize(text: str):
    """Unquote URL-encoded text and normalize to NFC form."""
    return unicodedata.normalize('NFC', unquote_plus(text))


def normalize_display_name(text: str):
    return DisplayName(unicode_unquote_normalize(text))


UnicodeValidator = BeforeValidator(unicode_unquote_normalize)
