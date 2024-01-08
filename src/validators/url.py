from annotated_types import Predicate
from rfc3986.validators import Validator

URLValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host').allow_schemes('http', 'https')
URIValidator = Validator().forbid_use_of_password().require_presence_of('scheme', 'host')

URLSafeValidator = Predicate(lambda s: not any(c in s for c in '/;.,?%#'))
