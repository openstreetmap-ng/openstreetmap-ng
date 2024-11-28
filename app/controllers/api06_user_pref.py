from typing import Annotated

from fastapi import APIRouter

from app.format import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.xml_body import xml_body
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import User
from app.models.scope import Scope
from app.models.types import Str255
from app.queries.user_pref_query import UserPrefQuery
from app.services.user_pref_service import UserPrefService

router = APIRouter(prefix='/api/0.6')


@router.get('/user/preferences')
@router.get('/user/preferences.xml')
@router.get('/user/preferences.json')
async def get_prefs(
    _: Annotated[User, api_user(Scope.read_prefs)],
):
    prefs = await UserPrefQuery.find_many_by_app(app_id=None)
    return Format06.encode_user_preferences(prefs)


@router.get('/user/preferences/{key}')
async def get_pref(
    key: Str255,
    _: Annotated[User, api_user(Scope.read_prefs)],
):
    pref = await UserPrefQuery.find_one_by_app_key(app_id=None, key=key)

    if pref is None:
        raise_for.pref_not_found(app_id=None, key=key)

    return pref.value


@router.put('/user/preferences')
async def update_prefs(
    data: Annotated[dict, xml_body('osm/preferences')],
    _: Annotated[User, api_user(Scope.write_prefs)],
):
    try:
        prefs = Format06.decode_user_preferences(data.get('preference', ()))
    except Exception as e:
        raise_for.bad_xml('preferences', str(e))

    await UserPrefService.upsert_many(prefs)


@router.put('/user/preferences/{key}')
async def update_pref(
    key: Str255,
    _: Annotated[User, api_user(Scope.write_prefs)],
):
    value = get_request()._body.decode()  # noqa: SLF001
    user_pref = Format06.decode_user_preferences(({'@k': key, '@v': value},))[0]
    await UserPrefService.upsert_one(user_pref)


@router.delete('/user/preferences/{key}')
async def delete_pref(
    key: Str255,
    _: Annotated[User, api_user(Scope.write_prefs)],
):
    await UserPrefService.delete_by_app_key(app_id=None, key=key)
