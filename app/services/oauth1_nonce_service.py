import logging
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.db import db
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.limits import OAUTH1_TIMESTAMP_VALIDITY
from app.models.db.oauth1_nonce import OAuth1Nonce
from app.models.validating.oauth1_nonce import OAuth1NonceValidating


class OAuth1NonceService:
    @staticmethod
    async def spend(nonce_str: str | None, timestamp: float | str | None) -> None:
        """
        Spend an OAuth1 nonce.

        Raises an exception if the nonce is invalid or has already been spent.
        """

        if not nonce_str or not timestamp:
            raise_for().oauth1_nonce_missing()

        try:
            created_at = datetime.fromtimestamp(int(timestamp))
            created_age = utcnow() - created_at
        except ValueError:
            logging.debug('OAuth nonce timestamp invalid %r', timestamp)
            raise_for().oauth1_bad_nonce()

        if created_age > OAUTH1_TIMESTAMP_VALIDITY or created_age < -OAUTH1_TIMESTAMP_VALIDITY:
            logging.debug('OAuth nonce timestamp expired %r', timestamp)
            raise_for().oauth1_timestamp_out_of_range()

        try:
            nonce = OAuth1Nonce(
                **OAuth1NonceValidating(
                    nonce=nonce_str,
                    created_at=created_at,
                ).to_orm_dict()
            )
        except ValidationError:
            logging.debug('OAuth nonce timestamp invalid %r', timestamp)
            raise_for().oauth1_bad_nonce()

        # TODO: normalize unicode globally?
        try:
            async with db() as session:
                session.add(nonce)
        except IntegrityError:
            logging.debug('OAuth nonce already spent (%r, %r)', nonce_str, timestamp)
            raise_for().oauth1_nonce_used()
