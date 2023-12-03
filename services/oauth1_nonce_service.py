import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from db import DB
from lib.exceptions import raise_for
from limits import OAUTH1_TIMESTAMP_VALIDITY
from models.db.oauth1_nonce import OAuth1Nonce
from utils import utcnow

# TODO: OAUTH1_NONCE_MAX_LENGTH


class OAuth1NonceService:
    @staticmethod
    async def spend(nonce: str | None, timestamp: float | str | None) -> None:
        """
        Spend an OAuth1 nonce.

        Raises an exception if the nonce is invalid or has already been spent.
        """

        if not nonce or not timestamp:
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

        # TODO: normalize unicode globally?
        try:
            async with DB() as session:
                session.add(
                    OAuth1Nonce(
                        nonce=nonce,
                        created_at=created_at,
                    )
                )
        # TODO: check exception type str255
        # except IntegrityError:
        #     logging.debug('OAuth nonce invalid %r', nonce)
        #     raise_for().oauth1_bad_nonce()
        except IntegrityError:
            logging.debug('OAuth nonce already spent (%r, %r)', nonce, timestamp)
            raise_for().oauth1_nonce_used()
