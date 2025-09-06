from zid import zid

from app.config import APP_DOMAIN
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.crypto import hash_bytes
from app.lib.exceptions_context import raise_for
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user_token import UserTokenEmailInit
from app.models.proto.server_pb2 import UserTokenStruct
from app.models.types import Email, UserId, UserTokenId
from app.queries.user_token_query import UserTokenQuery
from app.services.audit_service import audit
from app.services.email_service import EmailService
from speedup.buffered_rand import buffered_randbytes


class UserTokenEmailService:
    @staticmethod
    async def send_email(new_email: Email | None = None) -> None:
        """Send a confirmation email for account confirmation or email change."""
        user = auth_user(required=True)
        token = await _create_token(new_email)

        # Determine email template and subject based on operation type
        if new_email is None:
            # Account confirmation
            subject = t('user_mailer.signup_confirm.subject')
            template_name = 'email/account-confirm'
            template_data = {
                'token': UserTokenStructUtils.to_str(token),
                'app_domain': APP_DOMAIN,
            }
        else:
            # Email change
            subject = t('user_mailer.email_confirm.subject')
            template_name = 'email/email-change-confirm'
            template_data = {
                'new_email': new_email,
                'token': UserTokenStructUtils.to_str(token),
                'app_domain': APP_DOMAIN,
            }

        await EmailService.schedule(
            source=None,
            from_user_id=None,
            to_user=user,
            subject=subject,
            template_name=template_name,
            template_data=template_data,
        )

    @staticmethod
    async def confirm(
        token_struct: UserTokenStruct, *, is_account_confirm: bool
    ) -> None:
        """Confirm account activation or email change."""
        token_type = 'account_confirm' if is_account_confirm else 'email_change'
        token = await UserTokenQuery.find_by_token_struct(token_type, token_struct)
        if token is None:
            raise_for.bad_user_token_struct()

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT user_id, email_change_new FROM user_token
                WHERE id = %s AND type = %s
                FOR UPDATE
                """,
                (token_struct.id, token_type),
            ) as r:
                row: tuple[UserId, Email | None] | None = await r.fetchone()
                if row is None:
                    raise_for.bad_user_token_struct()
                user_id, new_email = row

            if new_email is not None:
                await conn.execute(
                    """
                    UPDATE "user"
                    SET email = %s, email_verified = TRUE
                    WHERE id = %s
                    """,
                    (new_email, user_id),
                )
                audit_extra = new_email
            else:
                async with await conn.execute(
                    """
                    UPDATE "user"
                    SET email_verified = TRUE
                    WHERE id = %s AND NOT email_verified
                    RETURNING email
                    """,
                    (user_id,),
                ) as r:
                    email_row: tuple[Email] | None = await r.fetchone()
                    audit_extra = (
                        f'{email_row[0]} - Account confirm' if email_row else None
                    )

            await conn.execute(
                'DELETE FROM user_token WHERE id = %s',
                (token_struct.id,),
            )

            if audit_extra is not None:
                await audit(
                    'change_email',
                    conn,
                    user_id=user_id,
                    extra=audit_extra,
                )


async def _create_token(new_email: Email | None) -> UserTokenStruct:
    """Create a new user email confirmation or change token."""
    user = auth_user(required=True)
    token_bytes = buffered_randbytes(32)
    token_id: UserTokenId = zid()  # type: ignore

    token_init: UserTokenEmailInit = {
        'id': token_id,
        'type': 'email_change' if new_email is not None else 'account_confirm',
        'user_id': user['id'],
        'user_email_hashed': hash_bytes(user['email']),
        'token_hashed': hash_bytes(token_bytes),
        'email_change_new': new_email,
    }

    async with db(True) as conn:
        await conn.execute(
            """
            INSERT INTO user_token (
                id, type, user_id, user_email_hashed,
                token_hashed, email_change_new
            )
            VALUES (
                %(id)s, %(type)s, %(user_id)s, %(user_email_hashed)s,
                %(token_hashed)s, %(email_change_new)s
            )
            """,
            token_init,
        )

    return UserTokenStruct(id=token_id, token=token_bytes)
