import re

from annotated_types import Predicate

from app.libc.email import validate_email

_hex_str_re = re.compile(r'^(?:[0-9a-f]{2})+$')

HexStrValidator = Predicate(lambda s: _hex_str_re.fullmatch(s))

# EmptyEmailStrValidator = Predicate(lambda s: Email.validate(s) if s else s)
EmailStrValidator = Predicate(lambda s: validate_email(s))

# _typed_element_id_re = re.compile(r'^[nwr][^0]\d*$')

# TypedElementIdValidator = Predicate(lambda s: _typed_element_id_re.fullmatch(s) is not None)

# _versioned_element_id_re = re.compile(r'^[nwr][^0]\d*v[^0]\d*$')

# VersionedElementIdValidator = Predicate(lambda s: _versioned_element_id_re.fullmatch(s) is not None)
