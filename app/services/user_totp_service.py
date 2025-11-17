from pydantic import SecretStr

from app.config import TOTP_MAX_ATTEMPTS_PER_WINDOW
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import decrypt, encrypt
from app.lib.standard_feedback import StandardFeedback
from app.lib.totp import totp_time_window, verify_totp_code
from app.lib.translation import t
from app.models.types import Password, UserId
from app.queries.user_totp_query import UserTOTPQuery
from app.services.audit_service import audit


class UserTOTPService:
    @staticmethod
    async def setup_totp(secret: SecretStr, code: str) -> None:
        """
        Set up TOTP for the current user.

        Verifies the provided code against the secret, then stores
        the encrypted secret in the database.
        """
        user = auth_user(required=True)
        user_id = user['id']

        if not verify_totp_code(secret, code):
            StandardFeedback.raise_error(
                'code', t('two_fa.error_invalid_or_expired_code')
            )

        secret_encrypted = encrypt(secret)

        async with db(True) as conn:
            result = await conn.execute(
                """
                INSERT INTO user_totp (user_id, secret_encrypted)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, secret_encrypted),
            )
            if result.rowcount:
                await audit('add_totp', conn)

    @staticmethod
    async def verify_totp(user_id: UserId, code: str) -> bool:
        """
        Verify a TOTP code for a user with replay prevention.

        This method:
        1. Retrieves the user's encrypted secret
        2. Decrypts it
        3. Verifies the code against the secret
        4. Prevents code reuse within the same time window (30s)
        5. Updates last_used_at on success

        Args:
            user_id: User ID to verify
            code: 6-digit TOTP code (0-999999)
            conn: Optional database connection

        Returns:
            True if code is valid and not replayed, False otherwise
        """
        async with db(True) as conn:
            # Get the user's TOTP credentials
            totp = await UserTOTPQuery.find_one_by_user_id(user_id, conn=conn)
            if not totp:
                return False

            # Rate limiting: check total attempts in current time window
            time_window = totp_time_window()
            async with await conn.execute(
                'SELECT COUNT(*) FROM user_totp_used_code WHERE user_id = %s AND time_window = %s',
                (user_id, time_window),
            ) as r:
                (attempts_count,) = await r.fetchone()

            if attempts_count >= TOTP_MAX_ATTEMPTS_PER_WINDOW:
                await audit(
                    'auth_fail',
                    user_id=user_id,
                    extra={'reason': 'rate_limited'},
                    conn=conn,
                )
                StandardFeedback.raise_error(
                    'code', t('two_fa.error_too_many_attempts')
                )

            # Decrypt the secret
            secret = decrypt(totp['secret_encrypted'])

            # Verify the code (convert to zero-padded string for TOTP verification)
            if not verify_totp_code(secret, code):
                # Record failed attempt (store actual attempted code for rate limiting)
                await conn.execute(
                    'INSERT INTO user_totp_used_code (user_id, code, time_window) VALUES (%s, %s, %s) ON CONFLICT (user_id, time_window, code) DO NOTHING',
                    (user_id, code, time_window),
                )

                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'invalid_code'},
                )
                return False

            # Prevent replay: check if this code was already used in any of the valid time windows
            # Try to insert the used code for t-1, t, and t+1 windows
            # If any window already has this code, rows_inserted will be less than 3
            async with await conn.execute(
                """
                WITH insert_attempts AS (
                    INSERT INTO user_totp_used_code (user_id, code, time_window)
                    VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s)
                    ON CONFLICT (user_id, time_window, code) DO NOTHING
                    RETURNING 1
                )
                SELECT COUNT(*) FROM insert_attempts
                """,
                (
                    user_id,
                    code,
                    time_window - 1,
                    user_id,
                    code,
                    time_window,
                    user_id,
                    code,
                    time_window + 1,
                ),
            ) as r:
                (rows_inserted,) = await r.fetchone()

            # If fewer than 3 rows were inserted, at least one window already had this code (replay attack)
            if rows_inserted != 3:
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'code_reused'},
                )
                return False

            # Update last_used_at
            await conn.execute(
                'UPDATE user_totp SET last_used_at = statement_timestamp() WHERE user_id = %s',
                (user_id,),
            )

            # Clean up old used codes (keep only last 3 time windows = 90 seconds)
            await conn.execute(
                'DELETE FROM user_totp_used_code WHERE user_id = %s AND time_window < %s',
                (user_id, time_window - 2),
            )

            return True

    @staticmethod
    async def remove_totp(
        *,
        password: Password | None,
        user_id: UserId | None = None,
    ) -> None:
        if password is None:
            assert user_id is not None
        else:
            assert user_id is None
            user = auth_user(required=True)
            user_id = user['id']

            from app.services.user_service import UserService  # noqa: PLC0415

            await UserService.verify_user_password(
                user,
                password,
                field_name=None,
                audit_failure='remove_totp_password',
            )

        async with db(True) as conn:
            result = await conn.execute(
                'DELETE FROM user_totp WHERE user_id = %s',
                (user_id,),
            )
            if result.rowcount:
                await conn.execute(
                    'DELETE FROM user_totp_used_code WHERE user_id = %s',
                    (user_id,),
                )
                await audit(
                    'remove_totp',
                    conn,
                    target_user_id=(user_id if password is None else None),
                )
