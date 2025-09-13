import asyncio
from collections import deque
from statistics import median
from time import perf_counter

from zid import zid

from app.db import db
from app.lib.crypto import hash_bytes
from app.lib.translation import t, translation_context
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user import User
from app.models.db.user_token import UserTokenInit
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import Email, UserTokenId
from app.queries.user_query import UserQuery
from app.services.audit_service import audit
from app.services.email_service import EmailService
from speedup.buffered_rand import buffered_randbytes

_SEND_EMAIL_LATENCY = deque[float]([0.1], maxlen=10)


class UserTokenResetPasswordService:
    @staticmethod
    async def send_email(email: Email) -> None:
        """Send a password reset request to the given email address (if registered)."""
        ts = perf_counter()
        to_user = await UserQuery.find_by_email(email)
        if to_user is None:
            # Simulate latency to harden against time-based attacks
            delay = median(_SEND_EMAIL_LATENCY) - (perf_counter() - ts)
            await asyncio.sleep(delay)
            return

        token = await _create_token(to_user)

        with translation_context(to_user['language']):
            subject = t('user_mailer.lost_password.subject')

        await EmailService.schedule(
            source=None,
            from_user_id=None,
            to_user=to_user,
            subject=subject,
            template_name='email/reset-password',
            template_data={'token': UserTokenStructUtils.to_str(token)},
        )

        _SEND_EMAIL_LATENCY.append(perf_counter() - ts)


async def _create_token(user: User) -> UserTokenStruct:
    """Create a new user reset password token."""
    user_id = user['id']
    user_email_hashed = hash_bytes(user['email'])
    token_bytes = buffered_randbytes(32)
    token_hashed = hash_bytes(token_bytes)

    token_id: UserTokenId = zid()  # type: ignore
    token_init: UserTokenInit = {
        'id': token_id,
        'type': 'reset_password',
        'user_id': user_id,
        'user_email_hashed': user_email_hashed,
        'token_hashed': token_hashed,
    }

    async with db(True) as conn:
        await conn.execute(
            """
            INSERT INTO user_token (
                id, type, user_id, user_email_hashed, token_hashed
            )
            VALUES (
                %(id)s, %(type)s, %(user_id)s, %(user_email_hashed)s, %(token_hashed)s
            )
            """,
            token_init,
        )
        await audit('request_reset_password', conn, extra={'uid': user_id})

    return UserTokenStruct(id=token_id, token=token_bytes)
