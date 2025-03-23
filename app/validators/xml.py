import re

from pydantic import AfterValidator

from app.lib.translation import t

_BAD_XML_RE = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\uFFFE\uFFFF]')  # XML/1.0


def _validate_xml_safe(v: str) -> str:
    if _BAD_XML_RE.search(v):
        raise ValueError(t('validations.invalid_characters'))
    return v


XMLSafeValidator = AfterValidator(_validate_xml_safe)
