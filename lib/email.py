import logging
from functools import partial

import anyio
from email_validator import EmailNotValidError, validate_email

from config import TEST_ENV


class Email:
    @staticmethod
    def validate(email: str) -> str:
        """
        Validate and normalize email address.

        Raises ValueError on error.

        >>> Email.normalize('example@ツ.ⓁⒾⒻⒺ')
        'example@ツ.life'
        """

        try:
            info = validate_email(email, check_deliverability=False, test_environment=TEST_ENV)
        except EmailNotValidError as e:
            logging.debug('Received invalid email address %r', email)
            raise ValueError('Invalid email address') from e

        return info.normalized

    @staticmethod
    async def validate_dns(email: str) -> None:
        """
        Validate deliverability of email address.

        Raises ValueError on error.
        """

        fn = partial(validate_email, check_deliverability=True, test_environment=TEST_ENV)

        try:
            await anyio.to_thread.run_sync(fn, email)
        except EmailNotValidError as e:
            logging.debug('Received invalid email address (dns check) %r', email)
            raise ValueError('Invalid email address') from e
