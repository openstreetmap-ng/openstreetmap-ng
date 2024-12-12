from urllib.parse import urlsplit

from sqlalchemy import delete, update

from app.config import APP_URL
from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.mail import MailSource
from app.models.db.user import User, UserStatus
from app.models.db.user_token_account_confirm import UserTokenAccountConfirm
from app.models.proto.server_pb2 import UserTokenStruct
from app.queries.user_token_query import UserTokenQuery
from app.services.email_service import EmailService


class UserTokenAccountConfirmService:
    @staticmethod
    async def send_email() -> None:
        """
        Send a confirmation email for the current user.
        """
        app_domain = urlsplit(APP_URL).netloc
        token = await _create_token()
        await EmailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=auth_user(required=True),
            subject=t('user_mailer.signup_confirm.subject'),
            template_name='email/account_confirm.jinja2',
            template_data={'token': UserTokenStructUtils.to_str(token), 'app_domain': app_domain},
        )

    @staticmethod
    async def confirm(token_struct: UserTokenStruct) -> None:
        """
        Confirm a user account.
        """
        token = await UserTokenQuery.find_one_by_token_struct(UserTokenAccountConfirm, token_struct)
        if token is None:
            raise_for.bad_user_token_struct()

        async with db_commit() as session:
            # prevent race conditions
            await session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})
            if (
                await session.execute(
                    delete(UserTokenAccountConfirm).where(UserTokenAccountConfirm.id == token_struct.id)
                )
            ).rowcount != 1:
                raise_for.bad_user_token_struct()
            await session.commit()
            await session.execute(
                update(User)
                .where(User.id == token.user_id, User.status == UserStatus.pending_activation)
                .values({User.status: UserStatus.active})
                .inline()
            )


async def _create_token() -> UserTokenStruct:
    """
    Create a new user account confirmation token.
    """
    user = auth_user(required=True)
    user_email_hashed = hash_bytes(user.email.encode())
    token_bytes = buffered_randbytes(32)
    token_hashed = hash_bytes(token_bytes)
    async with db_commit() as session:
        token = UserTokenAccountConfirm(
            user_id=user.id,
            user_email_hashed=user_email_hashed,
            token_hashed=token_hashed,
        )
        session.add(token)

    return UserTokenStruct(id=token.id, token=token_bytes)
