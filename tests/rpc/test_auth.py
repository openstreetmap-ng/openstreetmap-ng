from pydantic import SecretStr
from totp_rs import totp_generate

from app.lib.auth_context import auth_context
from app.lib.locale import DEFAULT_LOCALE
from app.lib.translation import translation_context
from app.models.proto.auth_pb2 import (
    Credentials,
    LoginRequest,
    LoginResponse,
    TransmitUserPassword,
)
from app.models.types import DisplayName
from app.queries.user_query import UserQuery
from app.services.user_totp_service import UserTOTPService


async def test_login_sets_auth_cookie(client):
    r = await client.post(
        '/rpc/auth.Service/Login',
        headers={'Content-Type': 'application/proto'},
        content=LoginRequest(
            credentials=Credentials(
                display_name_or_email='user2',
                password=TransmitUserPassword(legacy='anything'),
            ),
            remember=True,
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    response = LoginResponse.FromString(r.content)
    assert not response.HasField('passkey')
    assert not response.HasField('totp')
    assert not response.HasField('recovery')

    set_cookie = r.headers.get('set-cookie')
    assert set_cookie is not None
    assert 'auth=' in set_cookie
    assert 'max-age=' in set_cookie.lower()


async def test_login_returns_totp_challenge(client):
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None

    secret = SecretStr('JBSWY3DPEHPK3PXP')

    with auth_context(user):
        await UserTOTPService.remove_totp(password=None, user_id=user['id'])
    try:
        with translation_context(DEFAULT_LOCALE), auth_context(user):
            await UserTOTPService.setup_totp(
                secret,
                6,
                int(totp_generate(secret.get_secret_value(), digits=6)),
            )

        r = await client.post(
            '/rpc/auth.Service/Login',
            headers={'Content-Type': 'application/proto'},
            content=LoginRequest(
                credentials=Credentials(
                    display_name_or_email='user1',
                    password=TransmitUserPassword(legacy='anything'),
                ),
            ).SerializeToString(),
        )
        assert r.is_success, r.text

        response = LoginResponse.FromString(r.content)
        assert response.totp == 6
        assert r.headers.get('set-cookie') is None
    finally:
        with auth_context(user):
            await UserTOTPService.remove_totp(password=None, user_id=user['id'])
