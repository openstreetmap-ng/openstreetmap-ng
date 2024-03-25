import cython

from app.models.tag_style import TagStyle, TagStyleCollection
from app.validators.email import validate_email


@cython.cfunc
def _is_email_string(s: str) -> cython.char:
    try:
        validate_email(s)
        return True
    except ValueError:
        return False


@cython.cfunc
def _format_email(tag: TagStyleCollection, key_parts: list[str], values: list[str]) -> None:
    success: cython.char = False
    new_styles = []

    for value in values:
        if _is_email_string(value):
            success = True
            new_styles.append(TagStyle(value, 'email', f'mailto:{value}'))
        else:
            new_styles.append(TagStyle(value))

    if success:
        tag.values = new_styles


def configure_email_style(method_map: dict) -> None:
    method_map['email'] = _format_email
