import pytest
from pydantic import BaseModel

from app.models.types import Email
from app.validators.email import EmailValidating, validate_email_deliverability


def test_validating_email_type():
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
async def test_validate_email_deliverability(email: str, expected: bool):
    assert await validate_email_deliverability(email) == expected
