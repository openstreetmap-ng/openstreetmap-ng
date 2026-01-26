import logging
from collections.abc import Callable
from typing import Literal

from psycopg import AsyncConnection
from pydantic import SecretStr

from app.config import ENV
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.password_hash import PasswordHash
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User, user_is_test
from app.models.types import Password, UserId
from app.queries.user_token_query import UserTokenQuery
from app.services.audit_service import audit
from app.services.oauth2_token_service import OAuth2TokenService


class UserPasswordService:
    @staticmethod
    async def verify_password(
        user: User,
        password: Password,
        *,
        field_name: str | None = None,
        error_message: Literal['ignore'] | Callable[[], str] | None = None,
        audit_failure: str | None = None,
        skip_rehash: bool = False,
    ):
        user_id = user['id']

        async def check():
            # Test user accepts any password in non-prod environment
            if user_is_test(user):
                return ENV != 'prod'

            async with (
                db() as conn,
                await conn.execute(
                    """
                    SELECT password_pb
                    FROM user_password
                    WHERE user_id = %s
                    """,
                    (user_id,),
                ) as r,
            ):
                row = await r.fetchone()
                if row is None:
                    return False

            password_pb: bytes = row[0]
            verification = PasswordHash.verify(password_pb, password)
            if not verification.success:
                return False

            if not skip_rehash and verification.rehash_needed:
                new_password_pb = PasswordHash.hash(password)
                if new_password_pb is not None:
                    async with db(True) as conn:
                        result = await conn.execute(
                            """
                            UPDATE user_password
                            SET password_pb = %s
                            WHERE user_id = %s AND password_pb = %s
                            """,
                            (new_password_pb, user_id, password_pb),
                        )
                        if result.rowcount:
                            logging.debug('Rehashed password for user %d', user_id)

            if verification.schema_needed is not None:
                StandardFeedback.raise_error(
                    'password_schema', verification.schema_needed
                )

            return True

        if await check():
            return True
        if audit_failure is not None:
            await audit('auth_fail', user_id=user_id, extra={'reason': audit_failure})
        if error_message == 'ignore':
            return False
        if error_message is None:
            error_message = lambda: t('users.auth_failure.invalid_credentials')
        StandardFeedback.raise_error(field_name, error_message())

    @staticmethod
    async def set_password_unsafe(
        conn: AsyncConnection, user_id: UserId, password: Password
    ):
        """Set or update password for user (upsert)."""
        password_pb = PasswordHash.hash(password)
        assert password_pb is not None, 'Provided password schema cannot be used'
        await conn.execute(
            """
            INSERT INTO user_password (user_id, password_pb)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                password_pb = EXCLUDED.password_pb,
                updated_at = DEFAULT
            """,
            (user_id, password_pb),
        )

    @staticmethod
    async def update_password(
        *,
        old_password: Password,
        new_password: Password,
    ):
        """Update password for authenticated user."""
        user = auth_user(required=True)
        user_id = user['id']

        await UserPasswordService.verify_password(
            user,
            old_password,
            field_name='old_password',
            error_message=lambda: t('validation.password_is_incorrect'),
            skip_rehash=True,
        )

        async with db(True) as conn:
            await UserPasswordService.set_password_unsafe(conn, user_id, new_password)
            await audit('change_password', conn)

    @staticmethod
    async def reset_password(
        token: SecretStr,
        *,
        new_password: Password,
        revoke_other_sessions: bool,
    ):
        """Reset password via token."""
        token_struct = UserTokenStructUtils.from_str(token)
        user_token = await UserTokenQuery.find_by_token_struct(
            'reset_password', token_struct
        )
        if user_token is None:
            raise_for.bad_user_token_struct()
        user_id = user_token['user_id']

        if revoke_other_sessions:
            await OAuth2TokenService.revoke_by_client_id(
                SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
            )

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT 1 FROM user_token
                WHERE id = %s AND type = 'reset_password'
                FOR UPDATE
                """,
                (token_struct.id,),
            ) as r:
                if await r.fetchone() is None:
                    raise_for.bad_user_token_struct()

            await UserPasswordService.set_password_unsafe(conn, user_id, new_password)
            await conn.execute(
                'DELETE FROM user_token WHERE id = %s',
                (token_struct.id,),
            )
            await audit(
                'change_password', conn, user_id=user_id, extra={'reason': 'reset'}
            )
