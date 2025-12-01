import pytest

from app.lib.auth_context import auth_context
from app.lib.locale import DEFAULT_LOCALE
from app.lib.translation import translation_context
from app.models.types import DisplayName, Password
from app.queries.user_query import UserQuery
from app.queries.user_recovery_code_query import UserRecoveryCodeQuery
from app.services.user_recovery_code_service import UserRecoveryCodeService


@pytest.mark.extended
async def test_recovery_code_flow():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None

    user_id = user['id']
    password = Password(b'anything')

    with translation_context(DEFAULT_LOCALE), auth_context(user):
        # Generate codes
        codes = await UserRecoveryCodeService.generate_recovery_codes(password=password)
        assert len(set(codes)) == 8
        status = await UserRecoveryCodeQuery.get_status(user_id)
        assert status['num_remaining'] == 8

        # Verify one code successfully
        success = await UserRecoveryCodeService.verify_recovery_code(user_id, codes[0])
        assert success is True
        status = await UserRecoveryCodeQuery.get_status(user_id)
        assert status['num_remaining'] == 7

        # Verify reuse of the same code fails
        success = await UserRecoveryCodeService.verify_recovery_code(user_id, codes[0])
        assert success is False
        status = await UserRecoveryCodeQuery.get_status(user_id)
        assert status['num_remaining'] == 7

        # Verify invalid code fails
        success = await UserRecoveryCodeService.verify_recovery_code(user_id, 'invalid')
        assert success is False
        status = await UserRecoveryCodeQuery.get_status(user_id)
        assert status['num_remaining'] == 7
