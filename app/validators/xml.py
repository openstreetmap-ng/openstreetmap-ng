import re2
from pydantic import AfterValidator

from app.lib.translation import t

# XML/1.0
_BAD_XML_RE = re2.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\x{FFFE}\x{FFFF}]')


def _validate_xml_safe(v: str):
    if _BAD_XML_RE.search(v):
        raise ValueError(t('validations.invalid_characters'))
    return v


XMLSafeValidator = AfterValidator(_validate_xml_safe)
