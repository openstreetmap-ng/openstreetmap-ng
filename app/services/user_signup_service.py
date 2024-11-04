from urllib.parse import urlsplit

from pydantic import SecretStr
from sqlalchemy import delete, update

from app.config import APP_URL
from app.db import db_commit
from app.lib.auth_context import auth_context, auth_user
from app.lib.password_hash import PasswordHash, PasswordSchema
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import primary_translation_locale, t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.mail import MailSource
from app.models.db.user import User, UserStatus
from app.models.types import DisplayNameType, EmailType, PasswordType
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService
from app.services.system_app_service import SystemAppService
from app.services.user_token_account_confirm_service import UserTokenAccountConfirmService
from app.validators.email import validate_email_deliverability


class UserSignupService:
    @staticmethod
    async def signup(
        *,
        display_name: DisplayNameType,
        email: EmailType,
        password_schema: PasswordSchema | str,
        password: PasswordType,
        tracking: bool,
    ) -> SecretStr:
        """
        Create a new user.

        Returns a new user session token.
        """
        # some early validation
        if not await UserQuery.check_display_name_available(display_name):
            StandardFeedback.raise_error('display_name', t('validation.display_name_is_taken'))
        if not await UserQuery.check_email_available(email):
            StandardFeedback.raise_error('email', t('validation.email_address_is_taken'))
        if not await validate_email_deliverability(email):
            StandardFeedback.raise_error('email', t('validation.invalid_email_address'))

        password_pb = PasswordHash.hash(password_schema, password)
        if password_pb is None:
            raise AssertionError(f'Password schema {password_schema} cannot be used during registration')

        # TODO: purge stale pending terms accounts
        async with db_commit() as session:
            user = User(
                email=email,
                display_name=display_name,
                password_pb=password_pb,
                created_ip=get_request_ip(),
                status=UserStatus.pending_terms,
                auth_provider=None,  # TODO: support
                auth_uid=None,
                language=primary_translation_locale(),
                activity_tracking=tracking,
                crash_reporting=tracking,
            )
            session.add(user)

        return await SystemAppService.create_access_token('SystemApp.web', user_id=user.id)

    @staticmethod
    async def accept_terms() -> None:
        """
        Accept the terms of service and send a confirmation email.
        """
        user = auth_user(required=True)
        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == user.id, User.status == UserStatus.pending_terms)
                .values({User.status: UserStatus.pending_activation})
                .inline()
            )
            if (await session.execute(stmt)).rowcount != 1:
                return

        with auth_context(user, scopes=()):
            await UserSignupService.send_confirm_email()

    @staticmethod
    async def send_confirm_email() -> None:
        """
        Send a confirmation email for the current user.
        """
        app_domain = urlsplit(APP_URL).netloc
        token = await UserTokenAccountConfirmService.create()
        await EmailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=auth_user(required=True),
            subject=t('user_mailer.signup_confirm.subject'),
            template_name='email/account_confirm.jinja2',
            template_data={'token': UserTokenStructUtils.to_str(token), 'app_domain': app_domain},
        )

    @staticmethod
    async def abort_signup() -> None:
        """
        Abort the current signup process.
        """
        async with db_commit() as session:
            stmt = delete(User).where(
                User.id == auth_user(required=True).id,
                User.status == UserStatus.pending_terms,
            )
            await session.execute(stmt)
