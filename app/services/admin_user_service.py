from collections.abc import Awaitable, Callable
from typing import Any

from psycopg import AsyncConnection
from psycopg.sql import SQL, Composable

from app.config import ENV
from app.db import db
from app.lib.audit import audit
from app.lib.auth.password_hash import PasswordLike
from app.lib.standard.feedback import StandardFeedback
from app.lib.text.translation import t
from app.models.db.user import user_is_test
from app.models.proto.admin_users_types import Role
from app.models.types import DisplayName, Email, UserId
from app.queries.user_query import UserQuery
from app.services.user_password_service import UserPasswordService
from app.services.user_token_service import UserTokenService
from app.validators.email import validate_email_deliverability


class AdminUserService:
    @staticmethod
    async def update_user(
        *,
        user_id: UserId,
        display_name: DisplayName | None,
        email: Email | None,
        email_verified: bool,
        roles: list[Role],
        new_password: PasswordLike | None,
    ):
        roles.sort()
        if 'administrator' in roles and 'moderator' in roles:
            StandardFeedback.raise_error(
                'roles', 'administrator and moderator roles cannot be used together'
            )

        user = await UserQuery.find_by_id(user_id)
        if user is None:
            StandardFeedback.raise_error(None, 'User not found')

        assignments: list[Composable] = []
        params: list[Any] = []
        audits: list[Callable[[AsyncConnection], Awaitable[None]]] = []

        if display_name is not None:
            if not await UserQuery.check_display_name_available(
                display_name, user=user
            ):
                StandardFeedback.raise_error(
                    'display_name', t('validation.display_name_is_taken')
                )
            if (
                user_is_test(user)
                and display_name != user['display_name']
                and ENV != 'dev'
            ):
                StandardFeedback.raise_error(
                    'display_name', 'Changing test user display_name is disabled'
                )

            assignments.append(SQL('display_name = %s'))
            params.append(display_name)
            audits.append(
                lambda conn: audit(
                    'change_display_name',
                    conn,
                    target_user_id=user_id,
                    extra={'name': display_name},
                )
            )

        audit_email_extra = {}

        if email is not None:
            if user['email'] == email:
                StandardFeedback.raise_error(
                    'email', t('validation.new_email_is_current')
                )
            if user_is_test(user) and ENV != 'dev':
                StandardFeedback.raise_error(
                    'email', 'Changing test user email is disabled'
                )
            if not await UserQuery.check_email_available(email, user=user):
                StandardFeedback.raise_error(
                    'email', t('validation.email_address_is_taken')
                )
            if not await validate_email_deliverability(email):
                StandardFeedback.raise_error(
                    'email', t('validation.invalid_email_address')
                )

            assignments.append(SQL('email = %s'))
            params.append(email)
            audit_email_extra['email'] = email

        if user['email_verified'] != email_verified:
            assignments.append(SQL('email_verified = %s'))
            params.append(email_verified)
            audit_email_extra['verified'] = email_verified

        if audit_email_extra:
            audits.append(
                lambda conn: audit(
                    'change_email',
                    conn,
                    target_user_id=user_id,
                    extra=audit_email_extra,
                )
            )

        if new_password is not None:
            audits.append(
                lambda conn: audit(
                    'change_password',
                    conn,
                    target_user_id=user_id,
                )
            )

        if user['roles'] != roles:
            assignments.append(SQL('roles = %s'))
            params.append(roles)
            audits.append(
                lambda conn: audit(
                    'change_roles',
                    conn,
                    target_user_id=user_id,
                    extra={'roles': roles},
                )
            )

        query = SQL('UPDATE "user" SET {} WHERE id = %s').format(
            SQL(', ').join(assignments)
        )
        params.append(user_id)

        async with db(True) as conn:
            if ENV != 'test':  # Prevent admin user updates on the test instance
                if assignments:
                    await conn.execute(query, params)
                if email is not None:
                    await UserTokenService.delete_all_for_user(conn, user_id)
                if new_password is not None:
                    await UserPasswordService.set_password_unsafe(
                        conn, user_id, new_password
                    )
            for op in audits:
                await op(conn)
