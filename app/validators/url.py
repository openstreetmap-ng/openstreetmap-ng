from pydantic import AfterValidator
from rfc3986.validators import Validator

from app.config import URLSAFE_BLACKLIST
from app.lib.translation import t

_BLACKLIST_ISDISJOINT = frozenset(URLSAFE_BLACKLIST).isdisjoint


def _validate_url_safe(v: str) -> str:
    if not _BLACKLIST_ISDISJOINT(v):
        raise ValueError(t('validations.url_characters', characters=URLSAFE_BLACKLIST))
    return v


UrlValidator = (
    Validator()
    .forbid_use_of_password()
    .require_presence_of('scheme', 'host')
    .allow_schemes('http', 'https')
)
UriValidator = (
    Validator()  #
    .forbid_use_of_password()
    .require_presence_of('scheme', 'host')
)
UrlSafeValidator = AfterValidator(_validate_url_safe)
