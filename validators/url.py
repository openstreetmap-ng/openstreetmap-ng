from annotated_types import Predicate
from rfc3986.validators import Validator

_url_validator = Validator().require_presence_of('scheme', 'host').allow_schemes('http', 'https')

URLValidator = Predicate(lambda s: _url_validator.validate(s))

_uri_validator = Validator().require_presence_of('scheme', 'host')

URIValidator = Predicate(lambda s: _uri_validator.validate(s))

OOB_URIValidator = Predicate(lambda s: s == 'oob' or _uri_validator.validate(s))

URLSafeValidator = Predicate(lambda s: not any(c in s for c in '/;.,?%#'))
