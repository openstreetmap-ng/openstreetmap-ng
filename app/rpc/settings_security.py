from typing import override

from connectrpc.request import RequestContext
from pydantic import SecretStr

from app.lib.auth_context import auth_user, require_web_user
from app.lib.date_utils import datetime_unix
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.proto.settings_security_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.settings_security_pb2 import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    DisableTotpRequest,
    DisableTotpResponse,
    GenerateRecoveryCodesRequest,
    GenerateRecoveryCodesResponse,
    Passkey,
    RecoveryStatus,
    RegisterPasskeyRequest,
    RegisterPasskeyResponse,
    RemovePasskeyRequest,
    RemovePasskeyResponse,
    RenamePasskeyRequest,
    RenamePasskeyResponse,
    RevokeTokenRequest,
    RevokeTokenResponse,
    SetupTotpRequest,
    SetupTotpResponse,
)
from app.models.types import OAuth2TokenId
from app.queries.user_passkey_query import UserPasskeyQuery
from app.queries.user_recovery_code_query import UserRecoveryCodeQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.auth_service import AuthService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_password_service import UserPasswordService
from app.services.user_recovery_code_service import UserRecoveryCodeService
from app.services.user_totp_service import UserTOTPService


class _Service(Service):
    @override
    async def change_password(
        self, request: ChangePasswordRequest, ctx: RequestContext
    ):
        require_web_user()

        await UserPasswordService.update_password(
            old_password=request.old_password,
            new_password=request.new_password,
        )

        if request.revoke_other_sessions:
            current_session = await AuthService.authenticate_oauth2(None)
            assert current_session is not None
            await OAuth2TokenService.revoke_by_client_id(
                SYSTEM_APP_WEB_CLIENT_ID, skip_ids=[current_session['id']]
            )

        return ChangePasswordResponse(
            feedback=StandardFeedback.success_feedback(
                None, t('settings.password_has_been_changed')
            )
        )

    @override
    async def setup_totp(self, request: SetupTotpRequest, ctx: RequestContext):
        require_web_user()

        await UserTOTPService.setup_totp(
            SecretStr(request.secret),
            request.digits,
            request.totp_code,
        )

        totp = await UserTOTPQuery.find_one_by_user_id(auth_user(required=True)['id'])
        assert totp is not None
        return SetupTotpResponse(created_at=int(totp['created_at'].timestamp()))

    @override
    async def disable_totp(self, request: DisableTotpRequest, ctx: RequestContext):
        require_web_user()
        await UserTOTPService.remove_totp(password=request.password)
        return DisableTotpResponse()

    @override
    async def register_passkey(
        self, request: RegisterPasskeyRequest, ctx: RequestContext
    ):
        require_web_user()
        await UserPasskeyService.register_passkey(request.registration)
        return RegisterPasskeyResponse(passkeys=await _get_passkeys())

    @override
    async def rename_passkey(self, request: RenamePasskeyRequest, ctx: RequestContext):
        require_web_user()
        effective_name = await UserPasskeyService.rename_passkey(
            request.credential_id, name=request.name
        )
        if effective_name is None:
            StandardFeedback.raise_error('credential_id', 'Passkey not found')
        return RenamePasskeyResponse(name=effective_name)

    @override
    async def remove_passkey(self, request: RemovePasskeyRequest, ctx: RequestContext):
        require_web_user()
        await UserPasskeyService.remove_passkey(
            request.credential_id, password=request.password
        )
        return RemovePasskeyResponse(passkeys=await _get_passkeys())

    @override
    async def generate_recovery_codes(
        self, request: GenerateRecoveryCodesRequest, ctx: RequestContext
    ):
        require_web_user()
        codes = await UserRecoveryCodeService.generate_recovery_codes(
            password=request.password
        )
        return GenerateRecoveryCodesResponse(
            codes=codes,
            status=await _get_recovery_codes_status(),
        )

    @override
    async def revoke_token(self, request: RevokeTokenRequest, ctx: RequestContext):
        require_web_user()
        await OAuth2TokenService.revoke_by_id(OAuth2TokenId(request.token_id))
        return RevokeTokenResponse()


async def _get_passkeys():
    user_id = auth_user(required=True)['id']
    passkeys = await UserPasskeyQuery.find_all_by_user_id(user_id)

    result: list[Passkey] = []
    for passkey in passkeys:
        name = passkey['name']
        assert name is not None

        result.append(
            Passkey(
                credential_id=passkey['credential_id'],
                name=name,
                icons=passkey.get('icons', ()),
                created_at=int(passkey['created_at'].timestamp()),
            )
        )

    return result


async def _get_recovery_codes_status():
    user_id = auth_user(required=True)['id']
    status = await UserRecoveryCodeQuery.get_status(user_id)

    return RecoveryStatus(
        num_remaining=status['num_remaining'],
        created_at=datetime_unix(status['created_at']),
    )


service = _Service()
asgi_app_cls = ServiceASGIApplication
