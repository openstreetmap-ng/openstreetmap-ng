from zid import zid

from app.config import APP_DOMAIN
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user_token import UserTokenInit
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import UserId, UserTokenId
from app.queries.user_token_query import UserTokenQuery
from app.services.email_service import EmailService


class UserTokenAccountConfirmService:
    @staticmethod
    async def send_email() -> None:
        """Send a confirmation email for the current user."""
        token = await _create_token()
        await EmailService.schedule(
            source=None,
            from_user_id=None,
            to_user=auth_user(required=True),
            subject=t('user_mailer.signup_confirm.subject'),
            template_name='email/account-confirm',
            template_data={
                'token': UserTokenStructUtils.to_str(token),
                'app_domain': APP_DOMAIN,
            },
        )

    @staticmethod
    async def confirm(token_struct: UserTokenStruct) -> None:
        """Confirm a user account."""
        token = await UserTokenQuery.find_one_by_token_struct(
            'account_confirm', token_struct
        )
        if token is None:
            raise_for.bad_user_token_struct()

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT user_id FROM user_token
                WHERE id = %s AND type = 'account_confirm'
                FOR UPDATE
                """,
                (token_struct.id,),
            ) as r:
                row = await r.fetchone()
                if row is None:
                    raise_for.bad_user_token_struct()
                user_id: UserId = row[0]

            async with conn.pipeline():
                await conn.execute(
                    """
                    UPDATE "user"
                    SET email_verified = TRUE
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                await conn.execute(
                    """
                    DELETE FROM user_token
                    WHERE id = %s
                    """,
                    (token_struct.id,),
                )


async def _create_token() -> UserTokenStruct:
    """Create a new user account confirmation token."""
    user = auth_user(required=True)
    user_id = user['id']
    user_email_hashed = hash_bytes(user['email'])
    token_bytes = buffered_randbytes(32)
    token_hashed = hash_bytes(token_bytes)

    token_id: UserTokenId = zid()  # type: ignore
    token_init: UserTokenInit = {
        'id': token_id,
        'type': 'account_confirm',
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

    return UserTokenStruct(id=token_id, token=token_bytes)
