from pydantic import AfterValidator
from rfc3986.validators import Validator

from app.lib.translation import t
from app.limits import URLSAFE_BLACKLIST

_URLSAFE_ISDISJOINT = frozenset(URLSAFE_BLACKLIST).isdisjoint


def _validate_url_safe(v: str) -> str:
    if _URLSAFE_ISDISJOINT(v):
        raise ValueError(t('validations.url_characters', characters=URLSAFE_BLACKLIST))
    return v


UrlValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host').allow_schemes('http', 'https')
UriValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host')
UrlSafeValidator = AfterValidator(_validate_url_safe)
