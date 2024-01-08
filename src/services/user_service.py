import logging

from fastapi import UploadFile
from sqlalchemy import func

from src.db import DB
from src.lib.auth import auth_user
from src.lib.email import Email
from src.lib.message_collector import MessageCollector
from src.lib.translation import t
from src.models.auth_provider import AuthProvider
from src.models.avatar_type import AvatarType
from src.models.db.user import User
from src.models.editor import Editor
from src.models.geometry import PointGeometry
from src.models.str import EmailStr, PasswordStr, UserNameStr
from src.repositories.user_repository import UserRepository
from src.services.avatar_service import AvatarService
from src.services.email_change_service import EmailChangeService


class UserService:
    @staticmethod
    async def update_about_me(
        *,
        description: str,
    ) -> None:
        """
        Update user's about me.
        """

        async with DB() as session, session.begin():
            user = await session.get(User, auth_user().id, with_for_update=True)

            if user.description != description:
                user.description = description
                user.description_rich_hash = None

    @staticmethod
    async def update_settings(
        collector: MessageCollector,
        *,
        avatar_type: AvatarType | None,
        avatar_file: UploadFile | None,
        display_name: UserNameStr,
        editor: Editor | None,
        languages: str,
        home_point: PointGeometry | None,
    ) -> None:
        """
        Update user settings.
        """

        current_user = auth_user()

        # some early validation
        if not await UserRepository.check_display_name_available(display_name):
            collector.raise_error('display_name', t('user.display_name_already_taken'))

        # handle custom avatar
        if avatar_type == AvatarType.custom:
            avatar_id = await AvatarService.process_upload(avatar_file)
        else:
            avatar_id = None

        # update user data
        async with DB() as session, session.begin():
            user = await session.get(User, current_user.id, with_for_update=True)
            user.display_name = display_name
            user.editor = editor
            user.languages_str = languages
            user.home_point = home_point

            if avatar_type:
                user.avatar_type = avatar_type
                user.avatar_id = avatar_id

        # cleanup old avatar
        if avatar_type and current_user.avatar_id:
            await AvatarService.delete_by_id(current_user.avatar_id)

    @staticmethod
    async def update_email(
        collector: MessageCollector,
        *,
        new_email: EmailStr,
        password: str,
    ) -> None:
        """
        Update user email.

        Sends a confirmation email for the email change.
        """

        current_user = auth_user()

        # some early validation
        if current_user.email == new_email:
            return

        if not current_user.password_hasher.verify(password, current_user.password_hashed):
            collector.raise_error('password', t('user.invalid_password'))
        if not await UserRepository.check_email_available(new_email):
            collector.raise_error('email', t('user.email_already_taken'))
        if not await Email.validate_dns(new_email):
            collector.raise_error('email', t('user.invalid_email'))

        await EmailChangeService.send_confirm_email(new_email)
        collector.info('email', t('user.email_change_confirm_sent'))
        logging.debug('Sent email change confirmation for user %r', current_user.id)

    @staticmethod
    async def update_password(
        collector: MessageCollector,
        *,
        old_password: str,
        new_password: PasswordStr,
    ) -> None:
        """
        Update user password.
        """

        current_user = auth_user()

        # some early validation
        if not current_user.password_hasher.verify(old_password, current_user.password_hashed):
            collector.raise_error('old_password', t('user.invalid_password'))

        # precompute values to reduce transaction time
        password_hashed = current_user.password_hasher.hash(new_password)

        # update user data
        async with DB() as session, session.begin():
            user = await session.get(User, current_user.id, with_for_update=True)
            user.password_hashed = password_hashed
            user.password_changed_at = func.now()
            user.password_salt = None

        collector.success(None, t('user.password_changed'))
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
