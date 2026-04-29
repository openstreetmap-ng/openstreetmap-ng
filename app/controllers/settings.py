from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter
from starlette import status
from starlette.responses import RedirectResponse

from app.config import ACTIVE_SESSIONS_DISPLAY_LIMIT
from app.lib.auth_context import web_user
from app.lib.date_utils import datetime_unix
from app.lib.ip import anonymize_ip
from app.lib.render_response import render_proto_page
from app.lib.translation import t
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User
from app.models.proto.settings_connections_pb2 import Page as ConnectionsPage
from app.models.proto.settings_pb2 import EmailPage as SettingsEmailPage
from app.models.proto.settings_pb2 import Page as SettingsPage
from app.models.proto.settings_security_pb2 import Page as SecurityPage
from app.models.proto.settings_security_pb2 import Passkey, RecoveryStatus
from app.queries.audit_query import AuditQuery
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_passkey_query import UserPasskeyQuery
from app.queries.user_password_query import UserPasswordQuery
from app.queries.user_recovery_code_query import UserRecoveryCodeQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.auth_service import AuthService

router = APIRouter()


@router.get('/settings')
async def settings(user: Annotated[User, web_user()]):
    password_updated_at = (
        await UserPasswordQuery.get_updated_at(user['id']) or user['created_at']
    )

    return await render_proto_page(
        SettingsPage(
            email=user['email'],
            language=user['language'],
            password_updated_at=int(password_updated_at.timestamp()),
        ),
        title_prefix=t('accounts.edit.my settings').capitalize(),
    )


@router.get('/settings/email')
async def settings_email(user: Annotated[User, web_user()]):
    return await render_proto_page(
        SettingsEmailPage(email=user['email']),
        title_prefix=t('settings.email_settings'),
    )


@router.get('/settings/security')
async def settings_security(user: Annotated[User, web_user()]):
    async with TaskGroup() as tg:
        passkeys_t = tg.create_task(UserPasskeyQuery.find_all_by_user_id(user['id']))
        totp_t = tg.create_task(UserTOTPQuery.find_one_by_user_id(user['id']))
        recovery_codes_status_t = tg.create_task(
            UserRecoveryCodeQuery.get_status(user['id'])
        )
        current_t = tg.create_task(AuthService.authenticate_oauth2(None))
        active_sessions = await OAuth2TokenQuery.find_authorized_by_user_client_id(
            user_id=user['id'],
            client_id=SYSTEM_APP_WEB_CLIENT_ID,
            limit=ACTIVE_SESSIONS_DISPLAY_LIMIT,
        )
        tg.create_task(AuditQuery.resolve_last_activity(active_sessions))

    current_session = current_t.result()
    assert current_session is not None

    passkeys = [
        Passkey(
            credential_id=passkey['credential_id'],
            name=passkey['name'],  # type: ignore
            icons=passkey.get('icons', ()),
            created_at=int(passkey['created_at'].timestamp()),
        )
        for passkey in passkeys_t.result()
    ]

    recovery_codes_status = recovery_codes_status_t.result()
    recovery_codes_status_msg = RecoveryStatus(
        num_remaining=recovery_codes_status['num_remaining'],
        created_at=datetime_unix(recovery_codes_status['created_at']),
    )

    active_sessions_msg = []
    for session in active_sessions:
        authorized_at = session['authorized_at']
        assert authorized_at is not None

        last_activity = session.get('last_activity')
        active_sessions_msg.append(
            SecurityPage.Session(
                id=session['id'],
                authorized_at=int(authorized_at.timestamp()),
                current=session['id'] == current_session['id'],
                last_activity=(
                    SecurityPage.Session.Activity(
                        created_at=int(last_activity['created_at'].timestamp()),
                        ip=anonymize_ip(last_activity['ip']).packed,
                        user_agent=last_activity['user_agent'],
                    )
                    if last_activity is not None
                    else None
                ),
            )
        )

    return await render_proto_page(
        SecurityPage(
            email=user['email'],
            passkeys=passkeys,
            totp_created_at=(
                datetime_unix(totp['created_at'])
                if (totp := totp_t.result()) is not None
                else None
            ),
            recovery_codes_status=recovery_codes_status_msg,
            active_sessions=active_sessions_msg,
        ),
        title_prefix=t('settings.password_and_security'),
    )


@router.get('/settings/connections')
async def settings_connections(_: Annotated[User, web_user()]):
    accounts = await ConnectedAccountQuery.find_by_user()

    return await render_proto_page(
        ConnectionsPage(
            connected_providers=[account['provider'] for account in accounts],
        ),
        title_prefix=t('settings.connected_accounts'),
    )


@router.get('/preferences{_:path}')
@router.get('/account/edit')
@router.get('/user/{_:str}/account')
async def legacy_settings(_=None):
    return RedirectResponse('/settings', status.HTTP_301_MOVED_PERMANENTLY)
