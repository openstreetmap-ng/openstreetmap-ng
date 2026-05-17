import logging
from collections.abc import Callable
from typing import Literal

from psycopg import AsyncConnection
from pydantic import SecretStr

from app.config import ENV
from app.db import db, db_delete, db_fetchval, db_insert, db_update
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth import user_token
from app.lib.auth.context import auth_user
from app.lib.auth.password import PasswordHash, PasswordLike
from app.lib.standard.feedback import StandardFeedback
from app.lib.text.translation import t
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User, user_is_test
from app.models.types import UserId
from app.queries.user_token_query import UserTokenQuery
from app.services.oauth2_token_service import OAuth2TokenService


class UserPasswordService:
    @staticmethod
    async def verify_password(
        user: User,
        password: PasswordLike,
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

            password_pb = await db_fetchval(
                bytes,
                t"""
                    SELECT password_pb
                    FROM user_password
                    WHERE user_id = {user_id}
                """,
            )
            if password_pb is None:
                return False

            verification = PasswordHash.verify(password_pb, password)
            if not verification.success:
                return False

            if not skip_rehash and verification.rehash_needed:
                new_password_pb = PasswordHash.hash(password)
                if new_password_pb is not None:
                    rowcount = await db_update(
                        'user_password',
                        {'password_pb': new_password_pb},
                        where=t'user_id = {user_id} AND password_pb = {password_pb}',
                    )
                    if rowcount:
                        logging.debug('Rehashed password for user %d', user_id)

            if verification.schema_needed is not None:
                StandardFeedback.raise_error(
                    'password_schema', verification.schema_needed
                )

            return True

        if await check():
            return True
        if audit_failure is not None:
            audit('auth_fail', user_id=user_id, extra={'reason': audit_failure}).close()
        if error_message == 'ignore':
            return False
        if error_message is None:
            error_message = lambda: t('users.auth_failure.invalid_credentials')
        StandardFeedback.raise_error(field_name, error_message())

    @staticmethod
    async def set_password_unsafe(
        conn: AsyncConnection, user_id: UserId, password: PasswordLike
    ):
        """Set or update password for user (upsert)."""
        password_pb = PasswordHash.hash(password)
        assert password_pb is not None, 'Provided password schema cannot be used'
        await db_insert(
            'user_password',
            {'user_id': user_id, 'password_pb': password_pb},
            on_conflict=t"""(user_id) DO UPDATE SET
                password_pb = EXCLUDED.password_pb,
                updated_at = DEFAULT""",
            conn=conn,
        )

    @staticmethod
    async def update_password(
        *,
        old_password: PasswordLike,
        new_password: PasswordLike,
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
        new_password: PasswordLike,
        revoke_other_sessions: bool,
    ):
        """Reset password via token."""
        token_struct = user_token.parse(token)
        token_record = await UserTokenQuery.find_by_token_struct(
            'reset_password', token_struct
        )
        if token_record is None:
            raise_for.bad_user_token_struct()
        user_id = token_record['user_id']

        if revoke_other_sessions:
            await OAuth2TokenService.revoke_by_client_id(
                SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
            )

        token_id = token_struct.id
        async with db(True) as conn:
            exists = await db_fetchval(
                int,
                t"""
                    SELECT 1 FROM user_token
                    WHERE id = {token_id} AND type = 'reset_password'
                """,
                for_update=True,
                conn=conn,
            )
            if exists is None:
                raise_for.bad_user_token_struct()

            await UserPasswordService.set_password_unsafe(conn, user_id, new_password)
            await db_delete('user_token', where={'id': token_id}, conn=conn)
            await audit(
                'change_password', conn, user_id=user_id, extra={'reason': 'reset'}
            )
