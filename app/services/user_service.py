import logging

from fastapi import UploadFile
from pydantic import SecretStr
from sqlalchemy import delete, func, update

from app.config import FREEZE_TEST_USER
from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.locale import is_installed_locale
from app.lib.password_hash import PasswordHash
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.limits import USER_PENDING_EXPIRE, USER_SCHEDULED_DELETE_DELAY
from app.models.db.user import AvatarType, Editor, User, UserStatus
from app.models.types import DisplayNameType, EmailType, LocaleCode, PasswordType
from app.queries.user_query import UserQuery
from app.services.email_change_service import EmailChangeService
from app.services.image_service import ImageService
from app.services.system_app_service import SystemAppService
from app.validators.email import validate_email, validate_email_deliverability


class UserService:
    @staticmethod
    async def login(
        *,
        display_name_or_email: DisplayNameType | EmailType,
        password: PasswordType,
    ) -> SecretStr:
        """
        Attempt to login as a user.

        Returns a new user session token.
        """
        # TODO: normalize unicode & strip
        if '.' in display_name_or_email:  # (dot) indicates email format, display_name blacklists it
            try:
                email = validate_email(display_name_or_email)
            except ValueError:
                user = None
            else:
                user = await UserQuery.find_one_by_email(email)
        else:
            display_name = DisplayNameType(display_name_or_email)
            user = await UserQuery.find_one_by_display_name(display_name)

        if user is None:
            logging.debug('User not found %r', display_name_or_email)
            StandardFeedback.raise_error(None, t('users.auth_failure.invalid_credentials'))

        verification = PasswordHash.verify(
            password_pb=user.password_pb,
            password=password,
            is_test_user=user.is_test_user,
        )
        if not verification.success:
            logging.debug('Password mismatch for user %d', user.id)
            StandardFeedback.raise_error(None, t('users.auth_failure.invalid_credentials'))
        if verification.rehash_needed:
            await _rehash_user_password(user, password)
        if verification.schema_needed is not None:
            StandardFeedback.raise_error('password_schema', verification.schema_needed)

        logging.debug('Authenticated user %d using credentials', user.id)
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
            StandardFeedback.raise_error('display_name', t('validation.display_name_is_taken'))
        if not is_installed_locale(language):
            StandardFeedback.raise_error('language', t('validation.invalid_value'))
        user = auth_user(required=True)
        if user.is_test_user and FREEZE_TEST_USER and display_name != user.display_name:
            StandardFeedback.raise_error('display_name', 'Changing test user display_name is disabled')

        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == user.id)
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
        feedback: StandardFeedback,
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
            StandardFeedback.raise_error('email', t('validation.new_email_is_current'))
        if user.is_test_user and FREEZE_TEST_USER:
            StandardFeedback.raise_error('email', 'Changing test user email is disabled')

        verification = PasswordHash.verify(
            password_pb=user.password_pb,
            password=password,
            is_test_user=user.is_test_user,
        )
        if not verification.success:
            StandardFeedback.raise_error('password', t('validation.password_is_incorrect'))
        if verification.rehash_needed:
            await _rehash_user_password(user, password)
        if verification.schema_needed is not None:
            StandardFeedback.raise_error('password_schema', verification.schema_needed)
        if not await UserQuery.check_email_available(new_email):
            StandardFeedback.raise_error('email', t('validation.email_address_is_taken'))
        if not await validate_email_deliverability(new_email):
            StandardFeedback.raise_error('email', t('validation.invalid_email_address'))

        # TODO: send to old email too for security
        await EmailChangeService.send_confirm_email(new_email)
        feedback.info(None, t('settings.email_change_confirmation_sent'))

    @staticmethod
    async def update_password(
        feedback: StandardFeedback,
        *,
        old_password: PasswordType,
        new_password: PasswordType,
    ) -> None:
        """
        Update user password.
        """
        user = auth_user(required=True)
        verification = PasswordHash.verify(
            password_pb=user.password_pb,
            password=old_password,
            is_test_user=user.is_test_user,
        )
        if not verification.success:
            StandardFeedback.raise_error('old_password', t('validation.password_is_incorrect'))
        if verification.schema_needed is not None:
            StandardFeedback.raise_error('password_schema', verification.schema_needed)
        # ignore verification.rehash_needed, we are changing the password anyway

        new_password_pb = PasswordHash.hash(new_password)
        if new_password_pb is None:
            raise AssertionError('Provided password schemas cannot be used during update_password')

        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == user.id)
                .values(
                    {
                        User.password_pb: new_password_pb,
                        User.password_changed_at: func.statement_timestamp(),
                    }
                )
                .inline()
            )
            await session.execute(stmt)

        feedback.success(None, t('settings.password_has_been_changed'))
        logging.debug('Changed password for user %r', user.id)

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
                User.status == UserStatus.pending_activation,
                User.created_at < func.statement_timestamp() - USER_PENDING_EXPIRE,
            )
            await session.execute(stmt)


async def _rehash_user_password(user: User, password: PasswordType) -> None:
    new_password_pb = PasswordHash.hash(password)
    if new_password_pb is None:
        return

    async with db_commit() as session:
        stmt = (
            update(User)
            .where(User.id == user.id, User.password_pb == user.password_pb)
            .values({User.password_pb: new_password_pb})
            .inline()
        )
        await session.execute(stmt)
    logging.debug('Rehashed password for user %d', user.id)
