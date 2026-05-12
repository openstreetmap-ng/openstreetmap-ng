from urllib.parse import urlsplit

from pydantic import AfterValidator

from app.config import URLSAFE_BLACKLIST
from app.lib.translation import t

_BLACKLIST_ISDISJOINT = frozenset(URLSAFE_BLACKLIST).isdisjoint


def _validate_url_safe(v: str):
    if not _BLACKLIST_ISDISJOINT(v):
        raise ValueError(t('validations.url_characters', characters=URLSAFE_BLACKLIST))
    return v


def parse_uri(uri: str):
    """
    Parse a URI and enforce: scheme + host present, no password in userinfo.
    Raises ValueError on violation.
    """
    parsed = urlsplit(uri)
    if not parsed.scheme:
        raise ValueError('Missing URI scheme')
    if not parsed.hostname:
        raise ValueError('Missing URI host')
    if parsed.password is not None:
        raise ValueError('URI must not contain a password')
    return parsed


UrlSafeValidator = AfterValidator(_validate_url_safe)
