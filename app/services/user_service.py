import logging

from fastapi import UploadFile
from sqlalchemy import delete, func, or_, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.locale import is_installed_locale
from app.lib.message_collector import MessageCollector
from app.lib.password_hash import PasswordHash
from app.lib.translation import t
from app.limits import USER_PENDING_EXPIRE, USER_SCHEDULED_DELETE_DELAY
from app.models.db.user import AuthProvider, AvatarType, Editor, User, UserStatus
from app.models.types import DisplayNameType, EmailType, LocaleCode, PasswordType
from app.queries.user_query import UserQuery
from app.services.auth_service import AuthService
from app.services.image_service import ImageService
from app.services.system_app_service import SystemAppService
from app.validators.email import validate_email_deliverability


class UserService:
    @staticmethod
    async def login(
        *,
        display_name_or_email: str,
        password: PasswordType,
    ) -> str:
        """
        Attempt to log in a user.

        Returns a new user session token.
        """
        user = await AuthService.authenticate_credentials(display_name_or_email, password)
        if user is None:
            MessageCollector.raise_error(None, t('users.auth_failure.invalid_credentials'))
        return await SystemAppService.create_access_token('SystemApp.web', user_id=user.id)

    @staticmethod
    async def update_description(
        *,
        description: str,
    ) -> None:
        """
        Update user's profile description.
        """
        current_user = auth_user(required=True)
        if current_user.description == description:
            return
        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == current_user.id)
                .values(
                    {
                        User.description: description,
                        User.description_rich_hash: None,
                    }
                )
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def update_avatar(avatar_type: AvatarType, avatar_file: UploadFile) -> str:
        """
        Update user's avatar.

        Returns the new avatar URL.
        """
        data = await avatar_file.read()
        avatar_id = await ImageService.upload_avatar(data) if data and avatar_type == AvatarType.custom else None

        # update user data
        async with db_commit() as session:
            user = await session.get_one(User, auth_user(required=True).id, with_for_update=True)
            old_avatar_id = user.avatar_id
            user.avatar_type = avatar_type
            user.avatar_id = avatar_id

        # cleanup old avatar
        if old_avatar_id is not None:
            await ImageService.delete_avatar_by_id(old_avatar_id)

        return user.avatar_url

    @staticmethod
    async def update_background(background_file: UploadFile) -> str | None:
        """
        Update user's background.

        Returns the new background URL.
        """
        data = await background_file.read()
        background_id = await ImageService.upload_background(data) if data else None

        # update user data
        async with db_commit() as session:
            user = await session.get_one(User, auth_user(required=True).id, with_for_update=True)
            old_background_id = user.background_id
            user.background_id = background_id

        # cleanup old background
        if old_background_id is not None:
            await ImageService.delete_background_by_id(old_background_id)

        return user.background_url

    @staticmethod
    async def update_settings(
        *,
        display_name: DisplayNameType,
        language: LocaleCode,
        activity_tracking: bool,
        crash_reporting: bool,
    ) -> None:
        """
        Update user settings.
        """
        if not await UserQuery.check_display_name_available(display_name):
            MessageCollector.raise_error('display_name', t('validation.display_name_is_taken'))
        if not is_installed_locale(language):
            MessageCollector.raise_error('language', t('validation.invalid_value'))

        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == auth_user(required=True).id)
                .values(
                    {
                        User.display_name: display_name,
                        User.activity_tracking: activity_tracking,
                        User.crash_reporting: crash_reporting,
                        User.language: language,
                    }
                )
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def update_editor(
        editor: Editor | None,
    ) -> None:
        """
        Update default editor
        """
        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == auth_user(required=True).id)
                .values(
                    {
                        User.editor: editor,
                    }
                )
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def update_email(
        collector: MessageCollector,
        *,
        new_email: EmailType,
        password: PasswordType,
    ) -> None:
        """
        Update user email.

        Sends a confirmation email for the email change.
        """
        user = auth_user(required=True)
        if user.email == new_email:
            MessageCollector.raise_error('email', t('validation.new_email_is_current'))

        if not PasswordHash.verify(user.password_hashed, password, is_test_user=user.is_test_user).success:
            MessageCollector.raise_error('password', t('validation.password_is_incorrect'))
        if not await UserQuery.check_email_available(new_email):
            MessageCollector.raise_error('email', t('validation.email_address_is_taken'))
        if not await validate_email_deliverability(new_email):
            MessageCollector.raise_error('email', t('validation.invalid_email_address'))

        # await EmailChangeService.send_confirm_email(new_email)
        # TODO: send to old email too
        collector.info(None, t('settings.email_change_confirmation_sent'))

    @staticmethod
    async def update_password(
        collector: MessageCollector,
        *,
        old_password: PasswordType,
        new_password: PasswordType,
    ) -> None:
        """
        Update user password.
        """
        user = auth_user(required=True)
        if not PasswordHash.verify(user.password_hashed, old_password, is_test_user=user.is_test_user).success:
            MessageCollector.raise_error('old_password', t('validation.password_is_incorrect'))

        password_hashed = PasswordHash.hash(new_password)
        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == user.id)
                .values(
                    {
                        User.password_hashed: password_hashed,
                        User.password_changed_at: func.statement_timestamp(),
                    }
                )
                .inline()
            )
            await session.execute(stmt)

        collector.success(None, t('settings.password_has_been_changed'))
        logging.debug('Changed password for user %r', user.id)

    @staticmethod
    async def update_auth_provider(
        auth_provider: AuthProvider | None,
        auth_uid: str,
    ) -> None:
        """
        Update user auth provider.
        """
        # TODO: implement
        raise NotImplementedError

    # TODO: UI
    @staticmethod
    async def request_scheduled_delete() -> None:
        """
        Request a scheduled deletion of the user.
        """
        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == auth_user(required=True).id)
                .values(
                    {
                        User.scheduled_delete_at: func.statement_timestamp() + USER_SCHEDULED_DELETE_DELAY,
                    }
                )
                .inline()
            )
            await session.execute(stmt)

    @staticmethod
    async def abort_scheduled_delete() -> None:
        """
        Abort a scheduled deletion of the user.
        """
        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == auth_user(required=True).id)
                .values(
                    {
                        User.scheduled_delete_at: None,
                    }
                )
            )
            await session.execute(stmt)

    @staticmethod
    async def delete_old_pending_users():
        """
        Find old pending users and delete them.
        """
        logging.debug('Deleting old pending users')
        async with db_commit() as session:
            stmt = delete(User).where(
                or_(
                    User.status == UserStatus.pending_activation,
                    User.status == UserStatus.pending_terms,
                ),
                User.created_at < func.statement_timestamp() - USER_PENDING_EXPIRE,
            )
            await session.execute(stmt)
