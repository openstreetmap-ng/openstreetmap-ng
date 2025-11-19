from psycopg.rows import dict_row

from app.config import RECOVERY_CODE_MAX_ATTEMPTS, RECOVERY_CODE_RATE_LIMIT_WINDOW
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.recovery_code import generate_recovery_codes, verify_recovery_code
from app.lib.translation import t
from app.models.db.user_recovery_code import UserRecoveryCode
from app.models.types import Password, UserId
from app.services.audit_service import audit
from app.services.rate_limit_service import RateLimitService
from app.services.user_service import UserService


class UserRecoveryCodeService:
    @staticmethod
    async def generate_recovery_codes(*, password: Password) -> list[str]:
        """
        Generate or rotate recovery codes for a user.

        If password is None: initial generation (creates new codes).
        If password provided: rotation (verifies password, replaces codes).

        Returns the list of 8 recovery codes for one-time display.
        """
        user = auth_user(required=True)
        user_id = user['id']

        await UserService.verify_user_password(
            user,
            password,
            field_name='password',
            error_message=t('validation.password_is_incorrect'),
        )

        # Generate new codes
        display_codes, codes_hashed = generate_recovery_codes()

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO user_recovery_code (user_id, codes_hashed)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET codes_hashed = EXCLUDED.codes_hashed,
                    created_at = DEFAULT
                """,
                (user_id, codes_hashed),
            )
            await audit('generate_recovery_codes', conn)

        return display_codes

    @staticmethod
    async def verify_recovery_code(user_id: UserId, code: str) -> bool:
        """Verify a recovery code for a user."""
        await RateLimitService.update(
            key=f'recovery:{user_id}',
            change=1,
            quota=RECOVERY_CODE_MAX_ATTEMPTS,
            window=RECOVERY_CODE_RATE_LIMIT_WINDOW,
        )

        async with db(True) as conn:
            async with (
                await conn.cursor(row_factory=dict_row).execute(
                    """
                    SELECT * FROM user_recovery_code
                    WHERE user_id = %s
                    FOR UPDATE
                    """,
                    (user_id,),
                ) as r,
            ):
                recovery: UserRecoveryCode | None
                recovery = await r.fetchone()  # type: ignore
                if recovery is None:
                    await audit(
                        'auth_fail',
                        conn,
                        user_id=user_id,
                        extra={'reason': 'recovery_invalid'},
                    )
                    return False

            # Verify code
            code_index = verify_recovery_code(code, recovery['codes_hashed'])
            if code_index is None:
                await audit(
                    'auth_fail',
                    conn,
                    user_id=user_id,
                    extra={'reason': 'recovery_invalid'},
                )
                return False

            # Mark code as used
            await conn.execute(
                """
                UPDATE user_recovery_code
                SET codes_hashed[%s + 1] = NULL
                WHERE user_id = %s
                """,
                (code_index, user_id),
            )
            await audit(
                'use_recovery_code',
                conn,
                user_id=user_id,
                extra={'index': code_index},
            )
            return True
