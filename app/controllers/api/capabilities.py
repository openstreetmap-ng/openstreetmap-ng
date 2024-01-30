from fastapi import APIRouter

from app.lib.auth_context import auth_user
from app.lib.xmltodict import XAttr
from app.limits import (
    CHANGESET_QUERY_DEFAULT_LIMIT,
    CHANGESET_QUERY_MAX_LIMIT,
    ELEMENT_RELATION_MAX_MEMBERS,
    ELEMENT_WAY_MAX_NODES,
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
    user = auth_user()
    changeset_max_size = user.changeset_max_size if (user is not None) else UserRole.get_changeset_max_size(())

    return {
        'api': {
            'version': {
                # legacy capabilities endpoint only supports 0.6
                XAttr('minimum'): '0.6',
                XAttr('maximum'): '0.6',
            },
            'area': {
                XAttr('maximum'): min(MAP_QUERY_AREA_MAX_SIZE, TRACE_POINT_QUERY_AREA_MAX_SIZE),
            },
            'changesets': {
                XAttr('maximum_elements'): changeset_max_size,
                XAttr('default_query_limit'): CHANGESET_QUERY_DEFAULT_LIMIT,
                XAttr('maximum_query_limit'): CHANGESET_QUERY_MAX_LIMIT,
            },
            'note_area': {
                XAttr('maximum'): NOTE_QUERY_AREA_MAX_SIZE,
            },
            'notes': {
                XAttr('default_query_limit'): NOTE_QUERY_DEFAULT_LIMIT,
                XAttr('maximum_query_limit'): NOTE_QUERY_LEGACY_MAX_LIMIT,
            },
            'relationmembers': {
                XAttr('maximum'): ELEMENT_RELATION_MAX_MEMBERS,
            },
            'status': {
                # this is overly complicated, just check HTTP_503_SERVICE_UNAVAILABLE
                XAttr('database'): 'online',
                XAttr('api'): 'online',
                XAttr('gpx'): 'online',
            },
            'timeout': {
                XAttr('seconds'): 'TODO',  # TODO: timeout
            },
            'tracepoints': {
                XAttr('per_page'): TRACE_POINT_QUERY_DEFAULT_LIMIT,
            },
            'waynodes': {
                XAttr('maximum'): ELEMENT_WAY_MAX_NODES,
            },
        },
        'policy': {
            'imagery': {
                'blacklist': tuple({XAttr('regex'): entry} for entry in _legacy_imagery_blacklist),
            },
        },
    }
