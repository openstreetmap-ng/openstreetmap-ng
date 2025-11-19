from base64 import b32decode

from pydantic import SecretBytes, SecretStr

from app.lib.auth_context import auth_context
from app.lib.locale import DEFAULT_LOCALE
from app.lib.totp import _generate_totp_code, totp_time_window
from app.lib.translation import translation_context
from app.models.types import DisplayName, Password
from app.queries.user_query import UserQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.user_totp_service import UserTOTPService


def generate_code(secret_str: str) -> str:
    padding = '=' * (-len(secret_str) % 8)
    secret_bytes = SecretBytes(b32decode(secret_str.upper() + padding))
    return _generate_totp_code(secret_bytes, totp_time_window())


async def test_totp_flow():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None
    user_id = user['id']

    password = Password(SecretStr('anything'))
    secret_str = 'JBSWY3DPEHPK3PXP'
    secret = SecretStr(secret_str)

    # Ensure clean state
    await UserTOTPService.remove_totp(password=None, user_id=user_id)

    with translation_context(DEFAULT_LOCALE), auth_context(user):
        # Setup TOTP
        code = generate_code(secret_str)
        await UserTOTPService.setup_totp(secret, code)

        # Verify stored in DB
        stored_totp = await UserTOTPQuery.find_one_by_user_id(user_id)
        assert stored_totp is not None

        # Verify valid code
        current_code = generate_code(secret_str)
        success = await UserTOTPService.verify_totp(user_id, current_code)
        assert success is True

        # Verify replay protection (same code again)
        success = await UserTOTPService.verify_totp(user_id, current_code)
        assert success is False

        # Verify invalid code
        success = await UserTOTPService.verify_totp(user_id, '000000')
        assert success is False

        # Remove TOTP
        await UserTOTPService.remove_totp(password=password)

        # Verify removed
        stored_totp = await UserTOTPQuery.find_one_by_user_id(user_id)
        assert stored_totp is None
