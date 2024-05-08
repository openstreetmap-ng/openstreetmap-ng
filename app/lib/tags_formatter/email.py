import cython

from app.models.tag_format import TagFormat, TagFormatCollection
from app.validators.email import validate_email


@cython.cfunc
def _is_email_string(s: str) -> cython.char:
    try:
        validate_email(s)
    except ValueError:
        return False
    return True


def _format(tag: TagFormatCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_email_string(value):
            success = True
            new_styles.append(TagFormat(value, 'email', f'mailto:{value}'))
        else:
            new_styles.append(TagFormat(value))

    if success:
        tag.values = new_styles


def configure_email_format(method_map: dict) -> None:
    method_map['email'] = _format
