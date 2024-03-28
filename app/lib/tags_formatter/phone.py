import cython
import phonenumbers
from phonenumbers import (
    NumberParseException,
    PhoneNumberFormat,
    format_number,
    is_possible_number,
    is_valid_number,
)

from app.models.tag_format import TagFormat, TagFormatCollection


@cython.cfunc
def _get_phone_info(s: str):
    try:
        info = phonenumbers.parse(s, None)
    except NumberParseException:
        return None

    if not is_possible_number(info):
        return None
    if not is_valid_number(info):
        return None

    return info


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        info = _get_phone_info(value)
        if info is not None:
            success = True
            new_styles.append(TagFormat(value, 'phone', f'tel:{format_number(info, PhoneNumberFormat.E164)}'))
        else:
            new_styles.append(TagFormat(value))

    if success:
        tag.values = new_styles


def configure_phone_format(method_map: dict) -> None:
    method_map['phone'] = _format
    method_map['fax'] = _format
