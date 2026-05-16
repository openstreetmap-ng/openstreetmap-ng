from pydantic import SecretStr

from app.lib.auth.context import auth_context
from app.lib.text.locale import DEFAULT_LOCALE
from app.lib.text.translation import translation_context
from app.models.types import DisplayName
from app.queries.user_query import UserQuery
from app.services.auth_service import AuthService
from app.services.test_service import TestService
from app.services.user_recovery_code_service import UserRecoveryCodeService


async def test_login_with_recovery_codes_only_does_not_require_2fa():
    # Arrange - create a user with recovery codes
    display_name = DisplayName('user-recovery-only')
    await TestService.create_user(display_name)

    user = await UserQuery.find_by_display_name(display_name)
    assert user is not None

    with translation_context(DEFAULT_LOCALE), auth_context(user):
        await UserRecoveryCodeService.generate_recovery_codes(password=b'anything')

    # Act - attempt to login
    result = await AuthService.login(
        display_name_or_email=display_name,
        password=b'anything',
        passkey=None,
        totp_code=None,
        recovery_code=None,
    )

    # Assert - login should succeed without requiring 2FA
    assert isinstance(result, SecretStr)
