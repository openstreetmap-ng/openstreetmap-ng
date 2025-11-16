import logging

from psycopg import AsyncConnection

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import decrypt, encrypt
from app.lib.exceptions_context import raise_for
from app.lib.password_hash import PasswordHash
from app.lib.standard_feedback import StandardFeedback
from app.lib.totp import get_time_window, verify_totp_code
from app.lib.translation import t
from app.models.db.user import user_is_admin, user_is_test
from app.models.db.user_totp import UserTOTP
from app.models.types import Password, UserId
from app.queries.user_query import UserQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.audit_service import audit


class UserTOTPService:
    """User TOTP service for two-factor authentication."""

    # Maximum failed TOTP verification attempts per time window (30 seconds)
    MAX_FAILED_ATTEMPTS = 3
    # Sentinel value for marking failed attempts in user_totp_used_code table
    _FAILED_ATTEMPT_MARKER = -1

    @staticmethod
    async def setup_totp(
        *,
        secret: str,
        code: str,
    ) -> None:
        """
        Set up TOTP for the current user.

        Verifies the provided code against the secret, then stores
        the encrypted secret in the database.

        Args:
            secret: Base32-encoded TOTP secret (generated client-side)
            code: 6-digit TOTP code from authenticator app

        Raises:
            ValueError: If code verification fails
        """
        user = auth_user(required=True)
        user_id = user['id']

        # Verify the code before storing
        if not verify_totp_code(secret, code):
            StandardFeedback.raise_error('code', t('two_fa.error_invalid_or_expired_code'))

        # Encrypt the secret for storage
        secret_encrypted = encrypt(secret)

        async with db(write=True) as conn:
            # Check if user already has TOTP enabled
            existing = await UserTOTPQuery.find_one_by_user_id(user_id, conn=conn)
            if existing:
                StandardFeedback.raise_error('', t('two_fa.error_already_enabled'))

            # Store the encrypted secret
            await conn.execute(
                "INSERT INTO user_totp (user_id, secret_encrypted) VALUES (%s, %s)",
                (user_id, secret_encrypted),
            )

            await audit('add_2fa', conn)

        logging.info('User %d enabled 2FA', user_id)

    @staticmethod
    async def verify_totp(
        *,
        user_id: UserId,
        code: str,
        conn: AsyncConnection | None = None,
    ) -> bool:
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
            code: 6-digit TOTP code
            conn: Optional database connection

        Returns:
            True if code is valid and not replayed, False otherwise
        """
        async with db(write=True, conn=conn) as conn:
            # Get the user's TOTP credentials
            totp = await UserTOTPQuery.find_one_by_user_id(user_id, conn=conn)
            if not totp:
                return False

            # Rate limiting: check failed attempts in current time window
            time_window = get_time_window()
            async with await conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM user_totp_used_code WHERE user_id = %s AND time_window = %s AND code = %s",
                    (user_id, time_window, UserTOTPService._FAILED_ATTEMPT_MARKER),
                )
                (failed_attempts,) = await cursor.fetchone()

            if failed_attempts >= UserTOTPService.MAX_FAILED_ATTEMPTS:
                await audit('auth_fail', user_id=user_id, extra={'reason': 'rate_limited'}, conn=conn)
                StandardFeedback.raise_error('code', t('two_fa.error_too_many_attempts'))

            # Decrypt the secret
            secret = decrypt(totp['secret_encrypted'])

            # Verify the code
            if not verify_totp_code(secret, code):
                # Record failed attempt for rate limiting
                await conn.execute(
                    "INSERT INTO user_totp_used_code (user_id, code, time_window) VALUES (%s, %s, %s) ON CONFLICT (user_id, time_window, code) DO NOTHING",
                    (user_id, UserTOTPService._FAILED_ATTEMPT_MARKER, time_window),
                )

                await audit('auth_fail', user_id=user_id, extra={'reason': 'invalid_code'}, conn=conn)
                return False

            # Prevent replay: check if this code was already used in any of the valid time windows
            # Try to insert the used code for t-1, t, and t+1 windows
            # Using ON CONFLICT DO NOTHING and checking rows inserted
            code_int = int(code)
            async with await conn.cursor() as cursor:
                await cursor.execute(
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
                        user_id, code_int, time_window - 1,
                        user_id, code_int, time_window,
                        user_id, code_int, time_window + 1,
                    ),
                )
                (rows_inserted,) = await cursor.fetchone()

            # If no rows were inserted, all three windows already had this code (replay attack)
            if rows_inserted == 0:
                await audit('auth_fail', user_id=user_id, extra={'reason': 'code_reused'}, conn=conn)
                return False

            # Update last_used_at
            await conn.execute(
                "UPDATE user_totp SET last_used_at = statement_timestamp() WHERE user_id = %s",
                (user_id,),
            )

            # Clean up old used codes (keep only last 3 time windows = 90 seconds)
            await conn.execute(
                "DELETE FROM user_totp_used_code WHERE user_id = %s AND time_window < %s",
                (user_id, time_window - 2),
            )

            return True

    @staticmethod
    async def remove_totp(
        *,
        password: Password,
        target_user_id: UserId | None = None,
    ) -> None:
        """
        Remove TOTP for a user.

        If target_user_id is provided, this is an admin action.
        Otherwise, it's the current user removing their own 2FA.

        Args:
            password: Current user's password for verification (ignored for admin)
            target_user_id: User ID to remove 2FA from (admin only)
        """
        user = auth_user(required=True)
        user_id = user['id']

        # Determine if this is an admin action
        is_admin_action = target_user_id is not None and target_user_id != user_id

        if is_admin_action:
            # Admin removing another user's 2FA
            if not user_is_admin(user):
                raise_for().insufficient_scopes()

            target_id = target_user_id
        else:
            # User removing their own 2FA - verify password
            target_id = user_id

            # Verify password
            current_user = await UserQuery.find_one_by_id(user_id)
            if not current_user:
                raise_for().user_not_found(user_id)

            verification = PasswordHash.verify(
                password_pb=current_user['password_pb'],
                password=password,
                is_test_user=user_is_test(current_user),
            )

            if not verification.success:
                StandardFeedback.raise_error('password', t('two_fa.error_password_incorrect'))

        async with db(write=True) as conn:
            # Check if user has TOTP enabled
            totp = await UserTOTPQuery.find_one_by_user_id(target_id, conn=conn)
            if not totp:
                StandardFeedback.raise_error('', t('two_fa.error_not_enabled'))

            # Delete TOTP credentials
            await conn.execute(
                "DELETE FROM user_totp WHERE user_id = %s",
                (target_id,),
            )

            # Delete all used codes for this user
            await conn.execute(
                "DELETE FROM user_totp_used_code WHERE user_id = %s",
                (target_id,),
            )

            # Audit the removal
            if is_admin_action:
                await audit('remove_2fa', target_user_id=target_id, conn=conn)
            else:
                await audit('remove_2fa', conn=conn)

        logging.info(
            'User %d removed 2FA%s',
            target_id,
            f' by admin {user_id}' if is_admin_action else '',
        )
