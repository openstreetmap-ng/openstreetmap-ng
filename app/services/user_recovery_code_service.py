from fastapi import HTTPException
from psycopg.rows import dict_row
from pydantic import SecretBytes
from starlette import status

from app.config import RECOVERY_CODE_MAX_ATTEMPTS, RECOVERY_CODE_RATE_LIMIT_WINDOW
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import decrypt, encrypt
from app.lib.recovery_code import generate_recovery_codes, verify_recovery_code
from app.lib.translation import t
from app.models.db.user_recovery_code import UserRecoveryCode
from app.models.types import Password, UserId
from app.services.audit_service import audit
from app.services.rate_limit_service import RateLimitService
from app.services.user_service import UserService
from speedup.buffered_rand import buffered_randbytes


class UserRecoveryCodeService:
    @staticmethod
    async def generate_recovery_codes(*, password: Password | None = None) -> list[str]:
        """
        Generate or rotate recovery codes for a user.

        If password is None: initial generation (creates new secret).
        If password provided: rotation (verifies password, increments base_index).

        Returns the set of 8 recovery codes for one-time display.
        """
        user = auth_user(required=True)
        user_id = user['id']

        if password is None:
            # Initial generation
            secret = SecretBytes(buffered_randbytes(16))
            secret_encrypted = encrypt(secret)

            async with db(True) as conn:
                await conn.execute(
                    """
                    INSERT INTO user_recovery_code (user_id, secret_encrypted)
                    VALUES (%s, %s)
                    """,
                    (user_id, secret_encrypted),
                )
                await audit('generate_recovery_codes', conn)

            return generate_recovery_codes(secret, 0)

        # Rotation
        await UserService.verify_user_password(
            user,
            password,
            field_name='password',
            error_message=t('validation.password_is_incorrect'),
        )

        async with db(True) as conn:
            async with await conn.execute(
                """
                WITH rotated AS (
                    UPDATE user_recovery_code
                    SET base_index = base_index + 8,
                        created_at = DEFAULT
                    WHERE user_id = %(user_id)s
                    RETURNING secret_encrypted, base_index
                ),
                cleanup AS (
                    DELETE FROM user_recovery_code_used
                    WHERE user_id = %(user_id)s
                )
                SELECT * FROM rotated
                """,
                {'user_id': user_id},
            ) as r:
                secret_encrypted, base_index = await r.fetchone()  # type: ignore

            await audit('generate_recovery_codes', conn)

        return generate_recovery_codes(decrypt(secret_encrypted), base_index)

    @staticmethod
    async def verify_recovery_code(user_id: UserId, code: str) -> bool:
        """Verify a recovery code for a user."""
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
                recovery: UserRecoveryCode | None
                recovery = await r.fetchone()  # type: ignore
                if recovery is None:
                    await audit(
                        'auth_fail',
                        conn,
                        user_id=user_id,
                        extra={'reason': 'recovery_invalid'},
                    )
                    return False

            # Verify code
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

            # Mark code as used
            result = await conn.execute(
                """
                INSERT INTO user_recovery_code_used (user_id, code_offset)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, code_offset),
            )
            if not result.rowcount:
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'recovery_reused'},
                )
                return False

            await audit(
                'use_recovery_code',
                conn,
                user_id=user_id,
                extra={'index': code_offset},
            )
            return True
