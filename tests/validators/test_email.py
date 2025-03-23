import pytest
from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from pydantic import BaseModel, TypeAdapter

from app.config import PYDANTIC_CONFIG
from app.models.types import Email
from app.validators.email import EmailValidating, validate_email_deliverability

_EMAIL_VALIDATOR = TypeAdapter(EmailValidating, config=PYDANTIC_CONFIG)


@pytest.mark.parametrize(
    ('email', 'valid'),
    [
        ('example@gmail.com', True),
        (' example@gmail.com', False),  # Leading whitespace
        ('example@gmail.com ', False),  # Trailing whitespace
        ('example@gmail.com.', False),  # Dot at the end
        ('@gmail.com', False),  # Missing local part
        ('example@.com', False),  # Missing domain
        ('example@gmail.com@', False),  # Missing domain
        ('example@gmail.com@gmail.com', False),  # Multiple @
        ('a' * EMAIL_MAX_LENGTH + '@gmail.com', False),  # Too long
    ],
)
def test_email_validating(email, valid):
    try:
        _EMAIL_VALIDATOR.validate_python(email)
        assert valid
    except Exception:
        assert not valid


def test_email_validating_normalization():
    class TestModel(BaseModel):
        email: EmailValidating

    assert TestModel(email=Email('example@ツ.ⓁⒾⒻⒺ')).email == Email('example@ツ.life')


@pytest.mark.extended
@pytest.mark.parametrize(
    ('email', 'expected'),
    [
        ('example@gmail.com', True),
        ('example@invalid.localhost', False),
    ],
)
async def test_validate_email_deliverability(email, expected):
    assert await validate_email_deliverability(email) == expected
