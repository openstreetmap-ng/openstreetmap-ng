from base64 import b32decode

from psycopg import AsyncConnection
from pydantic import SecretBytes, SecretStr
from totp_rs import totp_time_window, totp_verify

from app.config import TOTP_MAX_ATTEMPTS_PER_WINDOW
from app.db import db, db_delete, db_fetchval, db_insert, db_insert_many
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.auth.crypto import decrypt, encrypt
from app.lib.auth.password import PasswordLike
from app.lib.standard.feedback import StandardFeedback
from app.lib.text.translation import t
from app.models.types import UserId
from app.queries.user_totp_query import UserTOTPQuery
from app.services.user_password_service import UserPasswordService


class UserTOTPService:
    @staticmethod
    async def setup_totp(secret: SecretStr, digits: int, code: int):
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

        code_str = f'{code:0{digits}d}'
        time_window = totp_time_window()
        if not totp_verify(
            secret_bytes.get_secret_value(),
            code_str,
            digits=digits,
            time_window=time_window,
        ):
            StandardFeedback.raise_error(
                'totp_code', t('two_fa.invalid_or_expired_authentication_code')
            )

        secret_encrypted = encrypt(secret_bytes)

        async with db(True) as conn:
            rowcount = await db_insert(
                'user_totp',
                {
                    'user_id': user_id,
                    'secret_encrypted': secret_encrypted,
                    'digits': digits,
                },
                on_conflict=t'DO NOTHING',
                conn=conn,
            )
            if rowcount:
                await _record_used_code(conn, user_id, code_str, time_window)
                await audit('add_totp', conn, extra={'digits': digits})

    @staticmethod
    async def verify_totp(user_id: UserId, code: int):
        """Verify a TOTP code for a user."""
        async with db(True) as conn:
            totp = await UserTOTPQuery.find_one_by_user_id(user_id, conn=conn)
            if totp is None:
                return False

            # Rate limit attempts in current time window
            time_window = totp_time_window()
            attempts_count = await db_fetchval(
                int,
                t"""
                    SELECT COUNT(*) FROM user_totp_used_code
                    WHERE user_id = {user_id} AND time_window = {time_window}
                """,
                conn=conn,
            )
            assert attempts_count is not None

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

            code_str = f'{code:0{totp["digits"]}d}'
            if not await _record_used_code(conn, user_id, code_str, time_window):
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'totp_reused'},
                )
                return False

            if not totp_verify(
                decrypt(totp['secret_encrypted']).get_secret_value(),
                code_str,
                digits=totp['digits'],
            ):
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'totp_invalid'},
                )
                return False

            # Cleanup old used codes
            await db_delete(
                'user_totp_used_code',
                where=t'user_id = {user_id} AND time_window < {time_window} - 1',
                conn=conn,
            )
            return True

    @staticmethod
    async def remove_totp(
        *,
        password: PasswordLike | None,
        user_id: UserId | None = None,
    ):
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

            await db_delete('user_totp', where={'user_id': user_id}, conn=conn)
            await db_delete(
                'user_totp_used_code', where={'user_id': user_id}, conn=conn
            )
            await audit(
                'remove_totp',
                conn,
                target_user_id=(user_id if password is None else None),
            )


async def _record_used_code(
    conn: AsyncConnection, user_id: UserId, code: str, time_window: int
):
    # Prevent replay: check if this code was already used in any of the valid time windows
    # Try to insert the used code for t-1, t, and t+1 windows
    # If any window already has this code, rows_inserted will be less than 3
    rowcount = await db_insert_many(
        'user_totp_used_code',
        [
            {'user_id': user_id, 'code': code, 'time_window': t'{time_window} - 1'},
            {'user_id': user_id, 'code': code, 'time_window': time_window},
            {'user_id': user_id, 'code': code, 'time_window': t'{time_window} + 1'},
        ],
        on_conflict=t'(user_id, time_window, code) DO NOTHING',
        conn=conn,
    )
    return rowcount == 3
