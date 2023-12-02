import re

from annotated_types import Predicate

# def validate_str255(value: str) -> str:
#     if len(value) > 255:
#         raise ValueError(f'String is too long: {len(value)} > 255')
#     return value


_hex_str_re = re.compile(r'^(?:[0-9a-f]{2})+$')

HexStrValidator = Predicate(lambda s: _hex_str_re.fullmatch(s))

# _typed_element_id_re = re.compile(r'^[nwr][^0]\d*$')

# TypedElementIdValidator = Predicate(lambda s: _typed_element_id_re.fullmatch(s) is not None)

# _versioned_element_id_re = re.compile(r'^[nwr][^0]\d*v[^0]\d*$')

# VersionedElementIdValidator = Predicate(lambda s: _versioned_element_id_re.fullmatch(s) is not None)
