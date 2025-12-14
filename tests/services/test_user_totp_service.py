import pytest
from pydantic import SecretStr
from totp_rs import totp_generate, totp_time_window

from app.lib.auth_context import auth_context
from app.lib.locale import DEFAULT_LOCALE
from app.lib.translation import translation_context
from app.models.types import DisplayName, Password
from app.queries.user_query import UserQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.user_totp_service import UserTOTPService


@pytest.mark.parametrize('digits', [6, 8])
async def test_totp_flow(digits: int):
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None
    user_id = user['id']

    password = Password(b'anything')
    secret_str = 'JBSWY3DPEHPK3PXP'
    secret = SecretStr(secret_str)

    # Ensure clean state
    await UserTOTPService.remove_totp(password=None, user_id=user_id)

    with translation_context(DEFAULT_LOCALE), auth_context(user):
        # Setup TOTP
        code = totp_generate(secret_str, digits=digits)
        await UserTOTPService.setup_totp(secret, digits, code)

        # Verify stored in DB
        stored_totp = await UserTOTPQuery.find_one_by_user_id(user_id)
        assert stored_totp is not None

        # Verify valid code
        current_code = totp_generate(
            secret_str, digits=digits, time_window=totp_time_window() + 1
        )
        success = await UserTOTPService.verify_totp(user_id, current_code)
        assert success is True

        # Verify replay protection (same code again)
        success = await UserTOTPService.verify_totp(user_id, current_code)
        assert success is False

        # Verify invalid code
        success = await UserTOTPService.verify_totp(user_id, '0' * digits)
        assert success is False

        # Remove TOTP
        await UserTOTPService.remove_totp(password=password)

        # Verify removed
        stored_totp = await UserTOTPQuery.find_one_by_user_id(user_id)
        assert stored_totp is None
