import logging
from base64 import urlsafe_b64decode
from datetime import datetime
from random import random

from psycopg import AsyncConnection

from app.config import PASSKEY_CHALLENGE_CLEANUP_PROBABILITY, PASSKEY_CHALLENGE_EXPIRE
from app.db import db, db_delete, db_insert
from speedup import buffered_randbytes


class UserPasskeyChallengeService:
    @staticmethod
    async def create():
        """Create a new passkey challenge."""
        challenge = buffered_randbytes(32)
        await db_insert('user_passkey_challenge', {'challenge': challenge})
        return challenge

    @staticmethod
    async def pop(challenge_b64: str) -> datetime | None:
        """Consume a challenge atomically. Returns created_at if valid."""
        challenge = urlsafe_b64decode(challenge_b64 + '==')

        async with db(True, autocommit=True) as conn:
            # probabilistic cleanup of expired challenges
            if random() < PASSKEY_CHALLENGE_CLEANUP_PROBABILITY:
                await _delete_expired(conn)

            row = await db_delete(
                'user_passkey_challenge',
                where=t"""challenge = {challenge}
                    AND created_at > statement_timestamp() - {PASSKEY_CHALLENGE_EXPIRE}""",
                returning='created_at',
                assert_returning=False,
                conn=conn,
            )
            return row[0] if row is not None else None


async def _delete_expired(conn: AsyncConnection):
    rowcount = await db_delete(
        'user_passkey_challenge',
        where=t'created_at <= statement_timestamp() - {PASSKEY_CHALLENGE_EXPIRE}',
        conn=conn,
    )
    if rowcount:
        logging.debug('Deleted %d expired passkey challenges', rowcount)
