import logging

from fastapi import UploadFile
from shapely import Point

from db import DB
from lib.auth import auth_user
from lib.email import Email
from lib.exceptions import raise_for
from lib.translation import t
from models.auth_provider import AuthProvider
from models.avatar_type import AvatarType
from models.db.user import User
from models.editor import Editor
from models.str import EmptyEmailStr, EmptyPasswordStr, UserNameStr
from repositories.user_repository import UserRepository
from services.avatar_service import AvatarService
from services.email_change_service import EmailChangeService


class UserService:
    @staticmethod
    async def update_profile(
        *,
        description: str,
        avatar_type: AvatarType | None,
        avatar_file: UploadFile | None,
        home_point: Point | None,
    ) -> None:
        """
        Update user profile.
        """

        current_user = auth_user()

        # handle custom avatar
        if avatar_type == AvatarType.custom:
            avatar_id = await AvatarService.process_upload(avatar_file)
        else:
            avatar_id = None

        # update user data
        async with DB() as session, session.begin():
            user = await session.get(User, current_user.id, with_for_update=True)
            user.home_point = home_point

            if user.description != description:
                user.description = description
                user.description_rich_hash = None

            if avatar_type:
                user.avatar_type = avatar_type
                user.avatar_id = avatar_id

        # cleanup old avatar
        if avatar_type and current_user.avatar_id:
            await AvatarService.delete_by_id(current_user.avatar_id)

    @staticmethod
    async def update_settings(
        *,
        display_name: UserNameStr,
        new_email: EmptyEmailStr,
        new_password: EmptyPasswordStr,
        auth_provider: AuthProvider | None,
        auth_uid: str,
        editor: Editor | None,
        languages: str,
    ) -> None:
        """
        Update user settings.
        """

        current_user = auth_user()

        # some early validation
        if not await UserRepository.check_display_name_available(display_name):
            raise_for().field_bad_request('display_name', t('user.display_name_already_taken'))

        # handle email change
        if new_email and new_email != current_user.email:
            if not await UserRepository.check_email_available(new_email):
                raise_for().field_bad_request('email', t('user.email_already_taken'))
            if not await Email.validate_dns(new_email):
                raise_for().field_bad_request('email', t('user.invalid_email'))

            await EmailChangeService.send_confirmation_email(new_email)

        # update user data
        async with DB() as session, session.begin():
            user = await session.get(User, current_user.id, with_for_update=True)
            user.display_name = display_name
            user.auth_provider = auth_provider
            user.auth_uid = auth_uid or None
            user.editor = editor
            user.languages_str = languages

            if new_password:
                user.password_hashed = user.password_hasher.hash(new_password)
                user.password_salt = None
                logging.debug('Changed password for user %r', user.id)
