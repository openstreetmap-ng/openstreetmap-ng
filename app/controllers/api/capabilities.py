from fastapi import APIRouter

from app.lib.auth_context import auth_user
from app.lib.xmltodict import xattr
from app.limits import (
    CHANGESET_QUERY_DEFAULT_LIMIT,
    CHANGESET_QUERY_MAX_LIMIT,
    ELEMENT_RELATION_MEMBERS_LIMIT,
    ELEMENT_WAY_MEMBERS_LIMIT,
    MAP_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_DEFAULT_LIMIT,
    NOTE_QUERY_LEGACY_MAX_LIMIT,
    TRACE_POINT_QUERY_AREA_MAX_SIZE,
    TRACE_POINT_QUERY_DEFAULT_LIMIT,
)
from app.models.user_role import UserRole

router = APIRouter()

_legacy_imagery_blacklist = (
    '.*\\.google(apis)?\\..*/.*',
    'http://xdworld\\.vworld\\.kr:8080/.*',
    '.*\\.here\\.com[/:].*',
    '.*\\.mapy\\.cz.*',
)


@router.get('/capabilities')
@router.get('/capabilities.xml')
@router.get('/capabilities.json')
@router.get('/0.6/capabilities')
@router.get('/0.6/capabilities.xml')
@router.get('/0.6/capabilities.json')
async def legacy_capabilities() -> dict:
    xattr_ = xattr  # read property once for performance
    user = auth_user()
    user_roles = user.roles if (user is not None) else ()
    changeset_max_size = UserRole.get_changeset_max_size(user_roles)

    return {
        'api': {
            'version': {
                # legacy capabilities endpoint only supports 0.6
                xattr_('minimum'): '0.6',
                xattr_('maximum'): '0.6',
            },
            'area': {
                xattr_('maximum'): min(MAP_QUERY_AREA_MAX_SIZE, TRACE_POINT_QUERY_AREA_MAX_SIZE),
            },
            'changesets': {
                xattr_('maximum_elements'): changeset_max_size,
                xattr_('default_query_limit'): CHANGESET_QUERY_DEFAULT_LIMIT,
                xattr_('maximum_query_limit'): CHANGESET_QUERY_MAX_LIMIT,
            },
            'note_area': {
                xattr_('maximum'): NOTE_QUERY_AREA_MAX_SIZE,
            },
            'notes': {
                xattr_('default_query_limit'): NOTE_QUERY_DEFAULT_LIMIT,
                xattr_('maximum_query_limit'): NOTE_QUERY_LEGACY_MAX_LIMIT,
            },
            'relationmembers': {
                xattr_('maximum'): ELEMENT_RELATION_MEMBERS_LIMIT,
            },
            'status': {
                # this is over-complicated, just check HTTP_503_SERVICE_UNAVAILABLE
                xattr_('database'): 'online',
                xattr_('api'): 'online',
                xattr_('gpx'): 'online',
            },
            'timeout': {
                xattr_('seconds'): 'TODO',  # TODO: timeout
            },
            'tracepoints': {
                xattr_('per_page'): TRACE_POINT_QUERY_DEFAULT_LIMIT,
            },
            'waynodes': {
                xattr_('maximum'): ELEMENT_WAY_MEMBERS_LIMIT,
            },
        },
        'policy': {
            'imagery': {
                'blacklist': tuple({xattr_('regex'): entry} for entry in _legacy_imagery_blacklist),
            },
        },
    }


@router.get('/versions')
@router.get('/versions.xml')
@router.get('/versions.json')
async def legacy_versions() -> dict:
    return {'api': {xattr('versions', custom_xml='version'): ('0.6',)}}
