import logging
from urllib.parse import urlsplit

from sqlalchemy import delete, update

from app.config import APP_URL
from app.db import db_autocommit
from app.lib.auth_context import auth_context, auth_user
from app.lib.message_collector import MessageCollector
from app.lib.password_hash import PasswordHash
from app.lib.translation import t, translation_languages
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.user import User
from app.models.mail_source import MailSource
from app.models.msgspec.user_token_struct import UserTokenStruct
from app.models.str import DisplayNameStr, EmailStr, PasswordStr
from app.models.user_status import UserStatus
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.mail_service import SMTP, MailService
from app.services.user_token_account_confirm_service import UserTokenAccountConfirmService
from app.validators.email import validate_email_deliverability

_app_domain: str = urlsplit(APP_URL).netloc


class UserSignupService:
    @staticmethod
    async def signup(
        collector: MessageCollector,
        *,
        display_name: DisplayNameStr,
        email: EmailStr,
        password: PasswordStr,
    ) -> UserTokenStruct:
        """
        Create a new user.

        Returns a new user session token.
        """

        # some early validation
        if not await UserRepository.check_display_name_available(display_name):
            collector.raise_error('display_name', t('form.display_name_taken'))
        if not await UserRepository.check_email_available(email):
            collector.raise_error('email', t('form.email_taken'))
        if not await validate_email_deliverability(email):
            collector.raise_error('email', t('form.email_invalid'))

        password_hashed = PasswordHash.default().hash(password.get_secret_value())
        created_ip = get_request_ip()
        languages = translation_languages()

        # TODO: purge stale pending terms accounts

        # create user
        async with db_autocommit() as session:
            user = User(
                email=email,
                display_name=display_name,
                password_hashed=password_hashed,
                created_ip=created_ip,
                status=UserStatus.pending_terms,
                auth_provider=None,  # TODO: support
                auth_uid=None,
                languages=languages,
            )
            session.add(user)

        return await AuthService.create_session(user.id)

    @staticmethod
    async def accept_terms() -> None:
        """
        Accept the terms of service and send a confirmation email.
        """

        user = auth_user()

        async with db_autocommit() as session:
            stmt = (
                update(User)
                .where(User.id == user.id, User.status == UserStatus.pending_terms)
                .values({User.status: UserStatus.pending_activation})
            )

            if (await session.execute(stmt)).rowcount != 1:
                return

        with auth_context(user, scopes=()):
            await UserSignupService.send_confirm_email()

            # auto-activate if smtp is not configured
            if SMTP is None:
                logging.info('Activating user %d (SMTP is not configured)', user.id)
                token = await UserTokenAccountConfirmService.create()
                await UserTokenAccountConfirmService.confirm(token)

    @staticmethod
    async def send_confirm_email() -> None:
        """
        Send a confirmation email for the current user.
        """

        token = await UserTokenAccountConfirmService.create()

        await MailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=auth_user(),
            subject=t('user_mailer.signup_confirm.subject'),
            template_name='email/account_confirm.jinja2',
            template_data={
                'app_domain': _app_domain,
                'token': str(token),
            },
        )

    @staticmethod
    async def abort_signup() -> None:
        """
        Abort the current signup process.
        """

        async with db_autocommit() as session:
            stmt = delete(User).where(User.id == auth_user().id, User.status == UserStatus.pending_terms)
            await session.execute(stmt)
