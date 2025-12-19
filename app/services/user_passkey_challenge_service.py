import logging
from base64 import urlsafe_b64decode
from datetime import datetime
from random import random

from psycopg import AsyncConnection

from app.config import PASSKEY_CHALLENGE_CLEANUP_PROBABILITY, PASSKEY_CHALLENGE_EXPIRE
from app.db import db
from speedup import buffered_randbytes


class UserPasskeyChallengeService:
    @staticmethod
    async def create() -> bytes:
        """Create a new passkey challenge."""
        challenge = buffered_randbytes(32)
        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO user_passkey_challenge (challenge)
                VALUES (%s)
                """,
                (challenge,),
            )
        return challenge

    @staticmethod
    async def pop(challenge_b64: str) -> datetime | None:
        """Consume a challenge atomically. Returns created_at if valid."""
        challenge = urlsafe_b64decode(challenge_b64 + '==')

        async with db(True, autocommit=True) as conn:
            # probabilistic cleanup of expired challenges
            if random() < PASSKEY_CHALLENGE_CLEANUP_PROBABILITY:
                await _delete_expired(conn)

            async with await conn.execute(
                """
                DELETE FROM user_passkey_challenge
                WHERE challenge = %s
                  AND created_at > statement_timestamp() - %s
                RETURNING created_at
                """,
                (challenge, PASSKEY_CHALLENGE_EXPIRE),
            ) as r:
                row = await r.fetchone()
                return row[0] if row is not None else None


async def _delete_expired(conn: AsyncConnection) -> None:
    result = await conn.execute(
        """
        DELETE FROM user_passkey_challenge
        WHERE created_at <= statement_timestamp() - %s
        """,
        (PASSKEY_CHALLENGE_EXPIRE,),
    )
    if result.rowcount:
        logging.debug('Deleted %d expired passkey challenges', result.rowcount)
