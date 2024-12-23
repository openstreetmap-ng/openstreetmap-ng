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
from app.models.db.user import User
from app.models.db.user_token_email_change import UserTokenEmailChange
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import EmailType
from app.queries.user_token_query import UserTokenQuery
from app.services.email_service import EmailService


class UserTokenEmailChangeService:
    @staticmethod
    async def send_email(new_email: EmailType) -> None:
        """
        Send a confirmation email for the email change.
        """
        app_domain = urlsplit(APP_URL).netloc
        token = await _create_token(new_email)
        await EmailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=auth_user(required=True),
            subject=t('user_mailer.email_confirm.subject'),
            template_name='email/email_change_confirm.jinja2',
            template_data={
                'new_email': new_email,
                'token': UserTokenStructUtils.to_str(token),
                'app_domain': app_domain,
            },
        )

    @staticmethod
    async def confirm(token_struct: UserTokenStruct) -> None:
        """
        Confirm a user email change.
        """
        token = await UserTokenQuery.find_one_by_token_struct(UserTokenEmailChange, token_struct)
        if token is None:
            raise_for.bad_user_token_struct()

        async with db_commit() as session:
            # prevent race conditions
            await session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})
            if (
                await session.execute(delete(UserTokenEmailChange).where(UserTokenEmailChange.id == token_struct.id))
            ).rowcount != 1:
                raise_for.bad_user_token_struct()
            await session.commit()
            await session.execute(
                update(User)  #
                .where(User.id == token.user_id)
                .values({User.email: token.new_email})
                .inline()
            )


async def _create_token(new_email: EmailType) -> UserTokenStruct:
    """
    Create a new user email change token.
    """
    user = auth_user(required=True)
    user_email_hashed = hash_bytes(user.email)
    token_bytes = buffered_randbytes(32)
    token_hashed = hash_bytes(token_bytes)
    async with db_commit() as session:
        token = UserTokenEmailChange(
            user_id=user.id,
            user_email_hashed=user_email_hashed,
            token_hashed=token_hashed,
            new_email=new_email,
        )
        session.add(token)
    return UserTokenStruct(id=token.id, token=token_bytes)
