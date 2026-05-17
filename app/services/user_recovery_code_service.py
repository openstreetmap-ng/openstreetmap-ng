from app.config import RECOVERY_CODE_MAX_ATTEMPTS, RECOVERY_CODE_RATE_LIMIT_WINDOW
from app.db import db, db_fetchone, db_insert
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.auth.password import PasswordLike
from app.lib.auth.recovery_code import generate_recovery_codes, verify_recovery_code
from app.lib.text.translation import t
from app.models.db.user_recovery_code import UserRecoveryCode
from app.models.types import UserId
from app.services.rate_limit_service import RateLimitService
from app.services.user_password_service import UserPasswordService


class UserRecoveryCodeService:
    @staticmethod
    async def generate_recovery_codes(*, password: PasswordLike):
        """
        Generate or rotate recovery codes for a user.

        If password is None: initial generation (creates new codes).
        If password provided: rotation (verifies password, replaces codes).

        Returns the list of 8 recovery codes for one-time display.
        """
        user = auth_user(required=True)
        user_id = user['id']

        await UserPasswordService.verify_password(
            user,
            password,
            field_name='password',
            error_message=lambda: t('validation.password_is_incorrect'),
        )

        # Generate new codes
        display_codes, codes_hashed = generate_recovery_codes()

        async with db(True) as conn:
            await db_insert(
                'user_recovery_code',
                {'user_id': user_id, 'codes_hashed': codes_hashed},
                on_conflict=t"""(user_id) DO UPDATE SET
                    codes_hashed = EXCLUDED.codes_hashed,
                    created_at = DEFAULT""",
                conn=conn,
            )
            await audit('generate_recovery_codes', conn)

        return display_codes

    @staticmethod
    async def verify_recovery_code(user_id: UserId, code: str):
        """Verify a recovery code for a user."""
        await RateLimitService.update(
            key=f'recovery:{user_id}',
            change=1,
            quota=RECOVERY_CODE_MAX_ATTEMPTS,
            window=RECOVERY_CODE_RATE_LIMIT_WINDOW,
            raise_on_limit=lambda: t(
                'two_fa.too_many_failed_attempts_please_try_again_in_one_minute'
            ),
        )

        async with db(True) as conn:
            recovery = await db_fetchone(
                UserRecoveryCode,
                t"""
                    SELECT * FROM user_recovery_code
                    WHERE user_id = {user_id}
                    FOR UPDATE
                """,
                conn=conn,
            )
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

            # Mark code as used (array element assignment requires raw SQL)
            await conn.execute(t"""
                UPDATE user_recovery_code
                SET codes_hashed[{code_index} + 1] = NULL
                WHERE user_id = {user_id}
            """)
            await audit(
                'use_recovery_code',
                conn,
                user_id=user_id,
                extra={'index': code_index},
            )
            return True
