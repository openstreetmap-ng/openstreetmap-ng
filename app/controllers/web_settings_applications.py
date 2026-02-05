from typing import Annotated

from fastapi import APIRouter, Form, Response, UploadFile
from starlette import status

from app.config import (
    OAUTH_APP_NAME_MAX_LENGTH,
    OAUTH_APP_URI_LIMIT,
    OAUTH_APP_URI_MAX_LENGTH,
    OAUTH_PAT_NAME_MAX_LENGTH,
)
from app.lib.auth_context import web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.db.user import User
from app.models.scope import scope_from_kwargs
from app.models.types import ApplicationId, OAuth2TokenId
from app.services.oauth2_application_service import OAuth2ApplicationService
from app.services.oauth2_token_service import OAuth2TokenService
from app.utils import id_response

router = APIRouter(prefix='/api/web')


@router.post('/settings/revoke-application')
async def settings_revoke_application(
    _: Annotated[User, web_user()],
    app_id: Annotated[ApplicationId, Form()],
):
    await OAuth2TokenService.revoke_by_app_id(app_id)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/settings/applications/admin/create')
async def settings_application_create(
    _: Annotated[User, web_user()],
    name: Annotated[str, Form(min_length=1, max_length=OAUTH_APP_NAME_MAX_LENGTH)],
):
    app_id = await OAuth2ApplicationService.create(name=name)
    return {'redirect_url': f'/settings/applications/admin/{app_id}/edit'}


@router.post('/settings/applications/admin/{app_id:int}/reset-client-secret')
async def settings_application_reset_client_secret(
    _: Annotated[User, web_user()],
    app_id: ApplicationId,
):
    client_secret = await OAuth2ApplicationService.reset_client_secret(app_id)
    return {'secret': client_secret.get_secret_value()}


@router.post('/settings/applications/admin/{app_id:int}/edit')
async def settings_application_update(
    _: Annotated[User, web_user()],
    app_id: ApplicationId,
    name: Annotated[str, Form(min_length=1, max_length=OAUTH_APP_NAME_MAX_LENGTH)],
    is_confidential: Annotated[bool, Form()],
    redirect_uris: Annotated[
        str, Form(max_length=OAUTH_APP_URI_LIMIT * (OAUTH_APP_URI_MAX_LENGTH + 4))
    ],
    read_prefs: Annotated[bool, Form()] = False,
    write_prefs: Annotated[bool, Form()] = False,
    write_api: Annotated[bool, Form()] = False,
    read_gpx: Annotated[bool, Form()] = False,
    write_gpx: Annotated[bool, Form()] = False,
    write_notes: Annotated[bool, Form()] = False,
    revoke_all_authorizations: Annotated[bool, Form()] = False,
):
    scopes = scope_from_kwargs(
        read_prefs=read_prefs,
        write_prefs=write_prefs,
        write_api=write_api,
        read_gpx=read_gpx,
        write_gpx=write_gpx,
        write_notes=write_notes,
    )
    await OAuth2ApplicationService.update_settings(
        app_id=app_id,
        name=name,
        is_confidential=is_confidential,
        redirect_uris=OAuth2ApplicationService.validate_redirect_uris(redirect_uris),
        scopes=scopes,
        revoke_all_authorizations=revoke_all_authorizations,
    )
    return StandardFeedback.success_result(None, t('settings.changes_have_been_saved'))


@router.post('/settings/applications/admin/{app_id:int}/avatar')
async def settings_application_upload_avatar(
    _: Annotated[User, web_user()],
    app_id: ApplicationId,
    avatar_file: Annotated[UploadFile, Form()],
):
    avatar_url = await OAuth2ApplicationService.update_avatar(app_id, avatar_file)
    return {'avatar_url': avatar_url}


@router.post('/settings/applications/admin/{app_id:int}/delete')
async def settings_application_delete(
    _: Annotated[User, web_user()],
    app_id: ApplicationId,
):
    await OAuth2ApplicationService.delete(app_id)
    return {'redirect_url': '/settings/applications/admin'}


@router.post('/settings/applications/token/create')
async def settings_application_tokens_create(
    _: Annotated[User, web_user()],
    name: Annotated[str, Form(min_length=1, max_length=OAUTH_PAT_NAME_MAX_LENGTH)],
    read_prefs: Annotated[bool, Form()] = False,
    write_prefs: Annotated[bool, Form()] = False,
    write_api: Annotated[bool, Form()] = False,
    read_gpx: Annotated[bool, Form()] = False,
    write_gpx: Annotated[bool, Form()] = False,
    write_notes: Annotated[bool, Form()] = False,
):
    scopes = scope_from_kwargs(
        read_prefs=read_prefs,
        write_prefs=write_prefs,
        write_api=write_api,
        read_gpx=read_gpx,
        write_gpx=write_gpx,
        write_notes=write_notes,
    )
    token_id = await OAuth2TokenService.create_pat(name=name, scopes=scopes)
    return id_response(token_id)


@router.post('/settings/applications/token/{token_id:int}/reset-access-token')
async def settings_application_tokens_reset_access_token(
    _: Annotated[User, web_user()],
    token_id: OAuth2TokenId,
):
    access_token = await OAuth2TokenService.reset_pat_access_token(token_id)
    return {'secret': access_token.get_secret_value()}


@router.post('/settings/applications/token/{token_id:int}/revoke')
async def settings_application_tokens_revoke(
    _: Annotated[User, web_user()],
    token_id: OAuth2TokenId,
):
    await OAuth2TokenService.revoke_by_id(token_id)
    return Response(None, status.HTTP_204_NO_CONTENT)
