from base64 import b32decode

from pydantic import SecretBytes, SecretStr

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
from app.services.user_password_service import UserPasswordService


class UserTOTPService:
    @staticmethod
    async def setup_totp(secret: SecretStr, digits: int, code: str) -> None:
        """
        Set up TOTP for the current user.

        Verifies the provided code against the secret, then stores
        the encrypted secret in the database.
        """
        user = auth_user(required=True)
        user_id = user['id']

        try:
            secret_value = secret.get_secret_value()
            secret_bytes = SecretBytes(
                b32decode(secret_value.upper() + '=' * (-len(secret_value) % 8))
            )
            del secret_value
        except Exception as e:
            raise ValueError('Invalid secret format') from e

        if not verify_totp_code(secret_bytes, digits, code):
            StandardFeedback.raise_error(
                'totp_code', t('two_fa.invalid_or_expired_authentication_code')
            )

        secret_encrypted = encrypt(secret_bytes)

        async with db(True) as conn:
            result = await conn.execute(
                """
                INSERT INTO user_totp (user_id, secret_encrypted, digits)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, secret_encrypted, digits),
            )
            if result.rowcount:
                await audit('add_totp', conn, extra={'digits': digits})

    @staticmethod
    async def verify_totp(user_id: UserId, code: str) -> bool:
        """Verify a TOTP code for a user."""
        async with db(True) as conn:
            totp = await UserTOTPQuery.find_one_by_user_id(user_id, conn=conn)
            if totp is None:
                return False

            # Rate limit attempts in current time window
            time_window = totp_time_window()
            async with await conn.execute(
                """
                SELECT COUNT(*) FROM user_totp_used_code
                WHERE user_id = %s AND time_window = %s
                """,
                (user_id, time_window),
            ) as r:
                (attempts_count,) = await r.fetchone()  # type: ignore

            if attempts_count >= TOTP_MAX_ATTEMPTS_PER_WINDOW:
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'totp_rate_limited'},
                )
                StandardFeedback.raise_error(
                    'totp_code',
                    t('two_fa.too_many_failed_attempts_please_try_again_in_one_minute'),
                )

            # Prevent replay: check if this code was already used in any of the valid time windows
            # Try to insert the used code for t-1, t, and t+1 windows
            # If any window already has this code, rows_inserted will be less than 3
            result = await conn.execute(
                """
                INSERT INTO user_totp_used_code (user_id, code, time_window)
                VALUES (%(user_id)s, %(code)s, %(time_window)s - 1),
                       (%(user_id)s, %(code)s, %(time_window)s),
                       (%(user_id)s, %(code)s, %(time_window)s + 1)
                ON CONFLICT (user_id, time_window, code) DO NOTHING
                """,
                {'user_id': user_id, 'code': code, 'time_window': time_window},
            )
            if result.rowcount != 3:
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'totp_reused'},
                )
                return False

            if not verify_totp_code(
                decrypt(totp['secret_encrypted']), totp['digits'], code
            ):
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'totp_invalid'},
                )
                return False

            # Cleanup old used codes
            await conn.execute(
                """
                DELETE FROM user_totp_used_code
                WHERE user_id = %s AND time_window < %s - 1
                """,
                (user_id, time_window),
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

            await UserPasswordService.verify_password(
                user,
                password,
                field_name='password',
                error_message=lambda: t('validation.password_is_incorrect'),
            )

        async with db(True) as conn:
            totp = await UserTOTPQuery.find_one_by_user_id(user_id, conn=conn)
            if totp is None:
                return

            await conn.execute(
                'DELETE FROM user_totp WHERE user_id = %s',
                (user_id,),
            )
            await conn.execute(
                'DELETE FROM user_totp_used_code WHERE user_id = %s',
                (user_id,),
            )
            await audit(
                'remove_totp',
                conn,
                target_user_id=(user_id if password is None else None),
            )
