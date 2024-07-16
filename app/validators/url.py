from annotated_types import Predicate
from rfc3986.validators import Validator

from app.limits import URLSAFE_BLACKLIST

UrlValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host').allow_schemes('http', 'https')
UriValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host')
UrlSafeValidator = Predicate(frozenset(URLSAFE_BLACKLIST).isdisjoint)
