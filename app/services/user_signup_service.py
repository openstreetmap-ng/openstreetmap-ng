import logging

from app.db import db
from app.lib.auth_context import auth_context
from app.lib.password_hash import PasswordHash
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import primary_translation_locale, t
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.user import UserInit
from app.models.types import DisplayName, Email, Password, UserId
from app.queries.user_query import UserQuery
from app.services.audit_service import audit
from app.services.user_token_email_service import UserTokenEmailService
from app.validators.email import validate_email_deliverability


class UserSignupService:
    @staticmethod
    async def signup(
        *,
        display_name: DisplayName,
        email: Email,
        password: Password,
        tracking: bool,
        email_verified: bool,
    ) -> UserId:
        """Create a new user. Returns the new user id."""
        if not await UserQuery.check_display_name_available(display_name):
            StandardFeedback.raise_error(
                'display_name', t('validation.display_name_is_taken')
            )
        if not await UserQuery.check_email_available(email):
            StandardFeedback.raise_error(
                'email', t('validation.email_address_is_taken')
            )
        if not await validate_email_deliverability(email):
            StandardFeedback.raise_error('email', t('validation.invalid_email_address'))

        password_pb = PasswordHash.hash(password)
        assert password_pb is not None, (
            'Provided password schemas cannot be used during signup'
        )

        user_init: UserInit = {
            'email': email,
            'email_verified': email_verified,
            'display_name': display_name,
            'password_pb': password_pb,
            'language': primary_translation_locale(),
            'activity_tracking': tracking,
            'crash_reporting': tracking,
            'created_ip': get_request_ip(),
        }

        async with (
            db(True) as conn,
            await conn.execute(
                """
                INSERT INTO "user" (
                    email, email_verified, display_name, password_pb,
                    language, activity_tracking, crash_reporting, created_ip
                )
                VALUES (
                    %(email)s, %(email_verified)s, %(display_name)s, %(password_pb)s,
                    %(language)s, %(activity_tracking)s, %(crash_reporting)s, %(created_ip)s
                )
                RETURNING id
                """,
                user_init,
            ) as r,
        ):
            user_id: UserId = (await r.fetchone())[0]  # type: ignore

        logging.debug('Created user %d', user_id)
        audit(
            'change_display_name',
            user_id=user_id,
            display_name=display_name,
            extra='Signup',
        )

        if email_verified:
            audit('change_email', user_id=user_id, email=email, extra='Signup')
        else:
            user = await UserQuery.find_one_by_id(user_id)
            assert user is not None, 'User must exist after creation'
            with auth_context(user, scopes=()):
                await UserTokenEmailService.send_email()

        return user_id
