from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse, Response

from app.lib.auth import user_token
from app.lib.auth.context import auth_user, web_user
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

_SOFTWARE_FILTERS = {
    'category': (
        {'value': 'editor', 'label': 'Editors'},
        {'value': 'mobile_editor', 'label': 'Mobile editors'},
        {'value': 'navigation', 'label': 'Navigation'},
        {'value': 'analysis', 'label': 'Analysis'},
        {'value': 'qa', 'label': 'Quality assurance'},
        {'value': 'visualization', 'label': 'Visualization'},
        {'value': 'imagery', 'label': 'Imagery'},
    ),
    'platform': (
        {'value': 'web', 'label': 'Web'},
        {'value': 'desktop', 'label': 'Desktop'},
        {'value': 'android', 'label': 'Android'},
        {'value': 'ios', 'label': 'iOS'},
    ),
    'license': (
        {'value': 'open_source', 'label': 'Open source'},
        {'value': 'proprietary', 'label': 'Proprietary'},
    ),
    'status': (
        {'value': 'active', 'label': 'Active development'},
        {'value': 'mature', 'label': 'Mature'},
    ),
}

_SOFTWARE_FILTER_LABELS = {
    key: {option['value']: option['label'] for option in options}
    for key, options in _SOFTWARE_FILTERS.items()
}

_SOFTWARE_ITEMS = (
    {
        'name': 'iD',
        'url': 'https://ideditor.com/',
        'image': '/static/img/brand/id.webp',
        'description': 'The default in-browser editor for quick OpenStreetMap edits.',
        'category': 'editor',
        'platforms': ('web',),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'Rapid',
        'url': 'https://rapideditor.org/',
        'image': '/static/img/brand/rapid.webp',
        'description': 'A web editor with assisted mapping tools and modern workflows.',
        'category': 'editor',
        'platforms': ('web',),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'JOSM',
        'url': 'https://josm.openstreetmap.de/',
        'image': '/static/img/brand/josm.webp',
        'description': 'A powerful desktop editor for advanced mapping and validation.',
        'category': 'editor',
        'platforms': ('desktop',),
        'license': 'open_source',
        'status': 'mature',
    },
    {
        'name': 'Vespucci',
        'url': 'https://vespucci.io/',
        'image': '/static/img/favicon/256.webp',
        'description': 'A full-featured OpenStreetMap editor for Android devices.',
        'category': 'mobile_editor',
        'platforms': ('android',),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'Go Map!!',
        'url': 'https://gomaposm.com/',
        'image': '/static/img/favicon/256.webp',
        'description': 'An iOS editor for surveying and editing OpenStreetMap outdoors.',
        'category': 'mobile_editor',
        'platforms': ('ios',),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'StreetComplete',
        'url': 'https://streetcomplete.app/',
        'image': '/static/img/favicon/256.webp',
        'description': 'A quest-based mobile editor for adding missing street details.',
        'category': 'mobile_editor',
        'platforms': ('android',),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'Every Door',
        'url': 'https://every-door.app/',
        'image': '/static/img/favicon/256.webp',
        'description': 'A mobile editor focused on shops, amenities, entrances, and POIs.',
        'category': 'mobile_editor',
        'platforms': ('android', 'ios'),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'OsmAnd',
        'url': 'https://osmand.net/',
        'image': '/static/img/favicon/256.webp',
        'description': 'Offline maps and navigation powered by OpenStreetMap data.',
        'category': 'navigation',
        'platforms': ('android', 'ios'),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'Organic Maps',
        'url': 'https://organicmaps.app/',
        'image': '/static/img/favicon/256.webp',
        'description': 'Offline maps and routing for travelers, hikers, and cyclists.',
        'category': 'navigation',
        'platforms': ('android', 'ios'),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'QGIS',
        'url': 'https://qgis.org/',
        'image': '/static/img/favicon/256.webp',
        'description': 'Desktop GIS software for analyzing and styling OpenStreetMap data.',
        'category': 'analysis',
        'platforms': ('desktop',),
        'license': 'open_source',
        'status': 'mature',
    },
    {
        'name': 'Overpass Turbo',
        'url': 'https://overpass-turbo.eu/',
        'image': '/static/img/brand/overpass.webp',
        'description': 'A web tool for querying and exploring OpenStreetMap data.',
        'category': 'analysis',
        'platforms': ('web',),
        'license': 'open_source',
        'status': 'mature',
    },
    {
        'name': 'MapRoulette',
        'url': 'https://maproulette.org/',
        'image': '/static/img/favicon/256.webp',
        'description': 'Task-based quality assurance and micro-mapping challenges.',
        'category': 'qa',
        'platforms': ('web',),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'uMap',
        'url': 'https://umap.openstreetmap.fr/',
        'image': '/static/img/favicon/256.webp',
        'description': 'Create and share custom maps using OpenStreetMap backgrounds.',
        'category': 'visualization',
        'platforms': ('web',),
        'license': 'open_source',
        'status': 'active',
    },
    {
        'name': 'Mapillary',
        'url': 'https://www.mapillary.com/',
        'image': '/static/img/favicon/256.webp',
        'description': 'Street-level imagery collection and browsing for map improvement.',
        'category': 'imagery',
        'platforms': ('web', 'android', 'ios'),
        'license': 'proprietary',
        'status': 'active',
    },
)


def _valid_software_filter(filter_name: str, value: str | None):
    if value is None:
        return ''
    allowed = _SOFTWARE_FILTER_LABELS[filter_name]
    return value if value in allowed else ''


def _software_matches_filters(item: dict, selected: dict[str, str]):
    category = selected['category']
    if category and item['category'] != category:
        return False

    platform = selected['platform']
    if platform and platform not in item['platforms']:
        return False

    license_ = selected['license']
    if license_ and item['license'] != license_:
        return False

    status_ = selected['status']
    return not status_ or item['status'] == status_


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
    token_struct = await user_token.parse_stateless(token)
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


@router.get('/software')
async def software(
    category: Annotated[str | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    license_: Annotated[str | None, Query(alias='license')] = None,
    status_: Annotated[str | None, Query(alias='status')] = None,
):
    selected = {
        'category': _valid_software_filter('category', category),
        'platform': _valid_software_filter('platform', platform),
        'license': _valid_software_filter('license', license_),
        'status': _valid_software_filter('status', status_),
    }
    software_items = [
        item for item in _SOFTWARE_ITEMS if _software_matches_filters(item, selected)
    ]

    return await render_response(
        'software',
        {
            'SOFTWARE_FILTERS': _SOFTWARE_FILTERS,
            'SOFTWARE_FILTER_LABELS': _SOFTWARE_FILTER_LABELS,
            'SOFTWARE_ITEMS': software_items,
            'SELECTED_FILTERS': selected,
        },
    )


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
