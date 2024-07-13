import logging

from fastapi import UploadFile
from sqlalchemy import delete, func, or_, update

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.locale import is_valid_locale
from app.lib.message_collector import MessageCollector
from app.lib.password_hash import PasswordHash
from app.lib.translation import t
from app.limits import USER_PENDING_EXPIRE
from app.models.auth_provider import AuthProvider
from app.models.avatar_type import AvatarType
from app.models.db.user import User
from app.models.editor import Editor
from app.models.msgspec.user_token_struct import UserTokenStruct
from app.models.str import DisplayNameStr, EmailStr, PasswordStr
from app.models.user_status import UserStatus
from app.queries.user_query import UserQuery
from app.services.auth_service import AuthService
from app.services.avatar_service import AvatarService
from app.services.email_change_service import EmailChangeService
from app.validators.email import validate_email_deliverability


class UserService:
    @staticmethod
    async def login(
        *,
        display_name_or_email: str,
        password: PasswordStr,
    ) -> UserTokenStruct:
        """
        Attempt to log in a user.

        Returns a new user session token.
        """
        user = await AuthService.authenticate_credentials(display_name_or_email, password)
        if user is None:
            MessageCollector.raise_error(None, t('users.auth_failure.invalid_credentials'))
        return await AuthService.create_session(user.id)

    @staticmethod
    async def update_about_me(
        *,
        description: str,
    ) -> None:
        """
        Update user's about me.
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
    async def update_avatar(
        avatar_type: AvatarType,
        avatar_file: UploadFile | None,
    ) -> str:
        """
        Update user's avatar.

        Returns the new avatar URL.
        """
        # handle custom avatar
        if avatar_type == AvatarType.custom and avatar_file is not None:
            avatar_id = await AvatarService.upload(avatar_file)
        else:
            avatar_id = None

        # update user data
        async with db_commit() as session:
            user = await session.get(User, auth_user(required=True).id, with_for_update=True)
            old_avatar_id = user.avatar_id
            user.avatar_type = avatar_type
            user.avatar_id = avatar_id

        # cleanup old avatar
        if old_avatar_id is not None:
            await AvatarService.delete_by_id(old_avatar_id)

        return user.avatar_url

    @staticmethod
    async def update_settings(
        *,
        display_name: DisplayNameStr,
        language: str,
        activity_tracking: bool,
        crash_reporting: bool,
    ) -> None:
        """
        Update user settings.
        """
        if not await UserQuery.check_display_name_available(display_name):
            MessageCollector.raise_error('display_name', t('user.name_already_taken'))
        # TODO: only display valid languages
        if not is_valid_locale(language):
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
        new_email: EmailStr,
        password: PasswordStr,
    ) -> None:
        """
        Update user email.

        Sends a confirmation email for the email change.
        """
        user = auth_user(required=True)
        if user.email == new_email:
            return

        if not PasswordHash.verify(user.password_hashed, password).success:
            MessageCollector.raise_error('password', t('user.invalid_password'))
        if not await UserQuery.check_email_available(new_email):
            MessageCollector.raise_error('email', t('user.email_already_taken'))
        if not await validate_email_deliverability(new_email):
            MessageCollector.raise_error('email', t('user.invalid_email'))

        await EmailChangeService.send_confirm_email(new_email)
        collector.info('email', t('user.email_change_confirm_sent'))

    @staticmethod
    async def update_password(
        collector: MessageCollector,
        *,
        old_password: PasswordStr,
        new_password: PasswordStr,
    ) -> None:
        """
        Update user password.
        """
        current_user = auth_user(required=True)
        if not PasswordHash.verify(current_user.password_hashed, old_password).success:
            MessageCollector.raise_error('old_password', t('user.invalid_password'))

        password_hashed = PasswordHash.hash(new_password)
        async with db_commit() as session:
            stmt = (
                update(User)
                .where(User.id == current_user.id)
                .values(
                    {
                        User.password_hashed: password_hashed,
                        User.password_changed_at: func.statement_timestamp(),
                    }
                )
                .inline()
            )
            await session.execute(stmt)

        collector.success(None, t('user.password_changed'))
        logging.debug('Changed password for user %r', current_user.id)

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
