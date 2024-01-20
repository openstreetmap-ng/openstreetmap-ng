import logging
from functools import partial

from anyio import to_thread
from email_validator import EmailNotValidError
from email_validator import validate_email as validate_email_

from app.config import TEST_ENV


def validate_email(email: str) -> str:
    """
    Validate and normalize email address.

    Raises ValueError on error.

    >>> validate_email('example@ツ.ⓁⒾⒻⒺ')
    'example@ツ.life'
    """

    try:
        info = validate_email_(
            email,
            check_deliverability=False,
            test_environment=TEST_ENV,
        )
    except EmailNotValidError as e:
        logging.debug('Received invalid email address %r', email)
        raise ValueError('Invalid email address') from e

    return info.normalized


async def validate_email_deliverability(email: str) -> None:
    """
    Validate deliverability of email address.

    Raises ValueError on error.
    """

    fn = partial(
        validate_email_,
        check_deliverability=True,
        test_environment=TEST_ENV,
    )

    try:
        await to_thread.run_sync(fn, email)
    except EmailNotValidError as e:
        logging.debug('Received invalid email address (dns check) %r', email)
        raise ValueError('Invalid email address') from e
