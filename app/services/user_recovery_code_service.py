from secrets import token_bytes

from fastapi import HTTPException
from psycopg.rows import dict_row
from pydantic import SecretBytes
from starlette import status

from app.config import RECOVERY_CODE_MAX_ATTEMPTS, RECOVERY_CODE_RATE_LIMIT_WINDOW
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import decrypt, encrypt
from app.lib.recovery_code import generate_recovery_codes, verify_recovery_code
from app.models.types import Password, UserId
from app.services.audit_service import audit
from app.services.rate_limit_service import RateLimitService
from app.services.user_service import UserService

# Implementation constant (not configurable)
_RECOVERY_CODE_COUNT = 8


class UserRecoveryCodeService:
    @staticmethod
    async def generate_recovery_codes(
        user_id: UserId, *, password: Password | None = None
    ) -> list[str]:
        """
        Generate or rotate recovery codes for a user.

        If password is None: initial generation (creates new secret, INSERT only).
        If password provided: rotation (verifies password, increments base_index by 8, UPDATE only).

        Returns the set of 8 recovery codes for one-time display.
        """
        if password is None:
            # Initial generation - create new secret
            secret_encrypted = encrypt(SecretBytes(token_bytes(16)))

            async with db(True) as conn:
                await conn.execute(
                    """
                    INSERT INTO user_recovery_code (user_id, secret_encrypted)
                    VALUES (%s, %s)
                    """,
                    (user_id, secret_encrypted),
                )
                await audit('generate_recovery_codes', conn)

            return generate_recovery_codes(decrypt(secret_encrypted), 0)

        else:
            # Rotation - verify password and increment base_index
            user = auth_user(required=True)
            if user['id'] != user_id:
                raise ValueError('User ID mismatch')

            await UserService.verify_user_password(
                user,
                password,
                field_name=None,
                audit_failure='rotate_recovery_codes_password',
            )

            async with db(True) as conn:
                async with await conn.execute(
                    """
                    UPDATE user_recovery_code
                    SET base_index = base_index + %s,
                        created_at = statement_timestamp()
                    WHERE user_id = %s
                    RETURNING secret_encrypted, base_index
                    """,
                    (_RECOVERY_CODE_COUNT, user_id),
                ) as r:
                    row = await r.fetchone()
                    if row is None:
                        raise ValueError('No recovery codes found')
                    secret_encrypted, base_index = row

                # Delete old used codes (cleanup)
                await conn.execute(
                    """
                    DELETE FROM user_recovery_code_used
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )

                await audit('generate_recovery_codes', conn)

            return generate_recovery_codes(decrypt(secret_encrypted), base_index)

    @staticmethod
    async def verify_recovery_code(user_id: UserId, code: str) -> bool:
        """
        Verify a recovery code for a user.

        Rate limits attempts, verifies the code using embedded index hint,
        and marks it as used if valid.
        """
        # Rate limit recovery code attempts
        try:
            await RateLimitService.update(
                key=f'recovery:{user_id}',
                change=1,
                quota=RECOVERY_CODE_MAX_ATTEMPTS,
                window=RECOVERY_CODE_RATE_LIMIT_WINDOW,
                raise_on_limit=True,
            )
        except HTTPException as e:
            if e.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                async with db(True) as conn:
                    await audit(
                        'auth_fail',
                        conn,
                        user_id=user_id,
                        extra={'reason': 'recovery_rate_limited'},
                    )
                raise
            raise

        async with db(True) as conn:
            async with (
                await conn.cursor(row_factory=dict_row).execute(
                    """
                        SELECT * FROM user_recovery_code
                        WHERE user_id = %s
                        FOR UPDATE
                    """,
                    (user_id,),
                ) as r,
            ):
                recovery = await r.fetchone()  # type: ignore

            if recovery is None:
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'recovery_invalid'},
                )
                return False

            # Verify code with O(1) lookup using embedded index
            code_offset = verify_recovery_code(
                decrypt(recovery['secret_encrypted']),
                recovery['base_index'],
                code,
            )

            if code_offset is None:
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'recovery_invalid'},
                )
                return False

            # Mark code as used (ON CONFLICT prevents replay)
            result = await conn.execute(
                """
                INSERT INTO user_recovery_code_used (user_id, code_offset)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, code_offset),
            )

            if result.rowcount == 0:
                # Code was already used (replay attack)
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'recovery_reused'},
                )
                return False

            # Success
            await audit(
                'use_recovery_code',
                conn,
                extra={'code_offset': code_offset},
            )
            return True
