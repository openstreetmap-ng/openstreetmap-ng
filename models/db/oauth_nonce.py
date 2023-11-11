import logging
from datetime import datetime
from typing import Annotated

from pydantic import Field, ValidationError

from lib.exceptions import Exceptions
from limits import OAUTH1_TIMESTAMP_VALIDITY
from models.db.base import Base
from models.str import Str255
from utils import utcnow

# TODO: timestamp expire


class OAuthNonce(Base):
    nonce: Annotated[Str255, Field(frozen=True)]
    created_at: Annotated[datetime, Field(frozen=True)]

    @classmethod
    async def spend(cls, nonce: str | None, timestamp: int | float | str | None) -> None:
        if not nonce or not timestamp:
            Exceptions.get().raise_for_oauth1_nonce_missing()

        try:
            created_at = datetime.fromtimestamp(int(timestamp))
            created_age = utcnow() - created_at
        except ValueError:
            logging.debug('OAuth nonce timestamp invalid %r', timestamp)
            Exceptions.get().raise_for_oauth1_bad_nonce()

        if created_age > OAUTH1_TIMESTAMP_VALIDITY or created_age < -OAUTH1_TIMESTAMP_VALIDITY:
            logging.debug('OAuth nonce timestamp expired %r', timestamp)
            Exceptions.get().raise_for_oauth1_timestamp_out_of_range()

        try:
            nonce_ = cls(nonce=nonce, created_at=created_at)
        except ValidationError:
            logging.debug('OAuth nonce invalid %r', nonce)
            Exceptions.get().raise_for_oauth1_bad_nonce()

        try:
            await nonce_.create()
        except Exception:
            # TODO: stricter exception type
            logging.debug('OAuth nonce already spent (%r, %r)', nonce, timestamp)
            Exceptions.get().raise_for_oauth1_nonce_used()
