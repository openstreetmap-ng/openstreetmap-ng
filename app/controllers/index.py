from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse, Response

from app.lib.auth.context import auth_user, web_user
from app.lib.auth.user_token_struct import UserTokenStructUtils
from app.lib.http.referrer import secure_referrer
from app.lib.render.proto import render_proto_page, render_response
from app.lib.text.locale import is_installed_locale
from app.lib.text.translation import t, translation_context
from app.middlewares.headers_middleware import CSP_HEADER
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.proto.about_pb2 import Page as AboutPage
from app.models.proto.communities_pb2 import Page as CommunitiesPage
from app.models.proto.copyright_pb2 import Page as CopyrightPage
from app.models.proto.fixthemap_pb2 import Page as FixthemapPage
from app.models.proto.help_pb2 import Page as HelpPage
from app.models.proto.login_pb2 import Page as LoginPage
from app.models.proto.welcome_pb2 import Page as WelcomePage
from app.models.types import ChangesetId, LocaleCode, NoteId, UserSubscriptionTargetId
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.user_token_unsubscribe_service import UserTokenUnsubscribeService

router = APIRouter()


@router.get('/')
@router.get('/export')
@router.get('/directions')
@router.get('/search')
@router.get('/query')
@router.get('/history')
@router.get('/history/nearby')
@router.get('/history/friends')
@router.get('/user/{_:str}/history')
@router.get('/note/new')
@router.get('/note/{_:int}')
@router.get('/changeset/{_:int}')
@router.get('/node/{_:int}')
@router.get('/node/{_:int}/history')
@router.get('/node/{_:int}/history/{__:int}')
@router.get('/way/{_:int}')
@router.get('/way/{_:int}/history')
@router.get('/way/{_:int}/history/{__:int}')
@router.get('/relation/{_:int}')
@router.get('/relation/{_:int}/history')
@router.get('/relation/{_:int}/history/{__:int}')
@router.get('/distance')
async def index():
    return await render_response('index/index')


@router.get('/changeset/{changeset_id:int}/unsubscribe')
async def get_changeset_unsubscribe(
    _: Annotated[User, web_user()],
    changeset_id: Annotated[ChangesetId, Path()],
):
    return await _get_unsubscribe('changeset', changeset_id)


@router.post('/changeset/{changeset_id:int}/unsubscribe')
async def post_changeset_unsubscribe(
    changeset_id: Annotated[ChangesetId, Path()],
    token: Annotated[SecretStr, Query(min_length=1)],
):
    return await _post_unsubscribe('changeset', changeset_id, token)


@router.get('/changeset/{changeset_id:int}/subscription')
async def legacy_changeset_subscription(changeset_id: ChangesetId):
    return RedirectResponse(f'/changeset/{changeset_id}/unsubscribe')


@router.get('/note/{note_id:int}/unsubscribe')
async def get_note_unsubscribe(
    _: Annotated[User, web_user()],
    note_id: Annotated[NoteId, Path()],
):
    return await _get_unsubscribe('note', note_id)


@router.post('/note/{note_id:int}/unsubscribe')
async def post_note_unsubscribe(
    note_id: Annotated[NoteId, Path()],
    token: Annotated[SecretStr, Query(min_length=1)],
):
    return await _post_unsubscribe('note', note_id, token)


@router.get('/note/{note_id:int}/subscription')
async def legacy_note_subscription(note_id: NoteId):
    return RedirectResponse(f'/note/{note_id}/unsubscribe')


async def _get_unsubscribe(
    unsubscribe_target: UserSubscriptionTarget,
    unsubscribe_id: UserSubscriptionTargetId,
    /,
):
    if not await UserSubscriptionQuery.is_subscribed(
        unsubscribe_target, unsubscribe_id
    ):
        return RedirectResponse(
            f'/{unsubscribe_target}/{unsubscribe_id}', status.HTTP_303_SEE_OTHER
        )
    return await index()


async def _post_unsubscribe(
    unsubscribe_target: UserSubscriptionTarget,
    unsubscribe_id: UserSubscriptionTargetId,
    /,
    token: SecretStr,
):
    token_struct = await UserTokenStructUtils.from_str_stateless(token)
    await UserTokenUnsubscribeService.unsubscribe(
        unsubscribe_target, unsubscribe_id, token_struct
    )
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.get('/communities')
async def communities():
    return await render_proto_page(
        CommunitiesPage(),
        title_prefix=t('layouts.communities'),
    )


@router.get('/copyright/{locale:str}')
async def copyright_i18n(locale: LocaleCode):
    if not is_installed_locale(locale):
        return Response(None, status.HTTP_404_NOT_FOUND)
    with translation_context(locale):
        title = t('layouts.copyright')
    return await render_proto_page(CopyrightPage(), title_prefix=title)


@router.get('/copyright')
async def copyright_():
    return await render_proto_page(CopyrightPage(), title_prefix=t('layouts.copyright'))


@router.get('/about/{locale:str}')
async def about_i18n(locale: LocaleCode):
    if not is_installed_locale(locale):
        return Response(None, status.HTTP_404_NOT_FOUND)
    with translation_context(locale):
        title = t('layouts.about')
    return await render_proto_page(AboutPage(), title_prefix=title)


@router.get('/about')
async def about():
    return await render_proto_page(AboutPage(), title_prefix=t('layouts.about'))


@router.get('/help')
async def help_():
    return await render_proto_page(HelpPage(), title_prefix=t('layouts.help'))


@router.get('/fixthemap')
async def fixthemap():
    return await render_proto_page(FixthemapPage(), title_prefix=t('fixthemap.title'))


@router.get('/login')
async def login(referer: Annotated[str | None, Query()] = None):
    if auth_user() is not None:
        return RedirectResponse(secure_referrer(referer), status.HTTP_303_SEE_OTHER)
    return await render_proto_page(LoginPage(), title_prefix=t('login.sign_in'))


@router.get('/welcome')
async def welcome(_: Annotated[User, web_user()]):
    return await render_proto_page(WelcomePage(), title_prefix=t('site.welcome.title'))


_EXPORT_EMBED_CSP_HEADER = CSP_HEADER.replace('frame-ancestors', 'frame-ancestors *', 1)


@router.get('/export/embed.html')
async def export_embed():
    response = await render_response('embed')
    response.headers['Content-Security-Policy'] = _EXPORT_EMBED_CSP_HEADER
    return response
