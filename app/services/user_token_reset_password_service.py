import asyncio
import time
from collections import deque
from statistics import median

from app.db import db_commit
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.translation import t, translation_context
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.mail import MailSource
from app.models.db.user import User
from app.models.db.user_token_reset_password import UserTokenResetPassword
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import EmailType
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService

_SEND_EMAIL_LATENCY: deque[float] = deque((0.1,), maxlen=10)


class UserTokenResetPasswordService:
    @staticmethod
    async def send_email(email: EmailType) -> None:
        """
        Send a password reset request to the given email address (if registered).
        """
        ts = time.perf_counter()
        to_user = await UserQuery.find_one_by_email(email)
        if to_user is None:
            # simulate latency to harden against time-based attacks
            delay = median(_SEND_EMAIL_LATENCY) - (time.perf_counter() - ts)
            await asyncio.sleep(delay)
            return

        token = await _create_token(to_user)
        with translation_context(to_user.language):
            subject = t('user_mailer.lost_password.subject')
        await EmailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=to_user,
            subject=subject,
            template_name='email/reset_password.jinja2',
            template_data={'token': UserTokenStructUtils.to_str(token)},
        )
        _SEND_EMAIL_LATENCY.append(time.perf_counter() - ts)


async def _create_token(user: User) -> UserTokenStruct:
    """
    Create a new user reset password token.
    """
    user_email_hashed = hash_bytes(user.email)
    token_bytes = buffered_randbytes(32)
    token_hashed = hash_bytes(token_bytes)
    async with db_commit() as session:
        token = UserTokenResetPassword(
            user_id=user.id,
            user_email_hashed=user_email_hashed,
            token_hashed=token_hashed,
        )
        session.add(token)
    return UserTokenStruct(id=token.id, token=token_bytes)
