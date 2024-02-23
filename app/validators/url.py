import cython
from annotated_types import Predicate
from rfc3986.validators import Validator

URLValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host').allow_schemes('http', 'https')
URIValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host')


@cython.cfunc
def _validate_urlsafe(text: str) -> bool:
    return all(c not in '/;.,?%#' for c in text)


URLSafeValidator = Predicate(_validate_urlsafe)
