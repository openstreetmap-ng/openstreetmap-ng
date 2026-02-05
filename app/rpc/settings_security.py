from typing import override

from connectrpc.request import RequestContext
from pydantic import SecretStr

from app.lib.auth_context import require_web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.proto.settings_security_connect import (
    SettingsSecurityService,
    SettingsSecurityServiceASGIApplication,
)
from app.models.proto.settings_security_pb2 import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    DisableTotpRequest,
    DisableTotpResponse,
    GenerateRecoveryCodesRequest,
    GenerateRecoveryCodesResponse,
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
from app.services.auth_service import AuthService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_password_service import UserPasswordService
from app.services.user_recovery_code_service import UserRecoveryCodeService
from app.services.user_totp_service import UserTOTPService


class _Service(SettingsSecurityService):
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
        return SetupTotpResponse()

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
        return RegisterPasskeyResponse()

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
        return RemovePasskeyResponse()

    @override
    async def generate_recovery_codes(
        self, request: GenerateRecoveryCodesRequest, ctx: RequestContext
    ):
        require_web_user()
        codes = await UserRecoveryCodeService.generate_recovery_codes(
            password=request.password
        )
        return GenerateRecoveryCodesResponse(codes=codes)

    @override
    async def revoke_token(self, request: RevokeTokenRequest, ctx: RequestContext):
        require_web_user()
        await OAuth2TokenService.revoke_by_id(OAuth2TokenId(request.token_id))
        return RevokeTokenResponse()


service = _Service()
asgi_app_cls = SettingsSecurityServiceASGIApplication
