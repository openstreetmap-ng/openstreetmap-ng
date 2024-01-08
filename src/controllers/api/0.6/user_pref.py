from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Request

from src.lib.auth import api_user
from src.lib.exceptions import raise_for
from src.lib.format.format06 import Format06
from src.lib_cython.xmltodict import XMLToDict
from src.models.db.user import User
from src.models.scope import Scope
from src.models.str import Str255
from src.repositories.user_pref_repository import UserPrefRepository
from src.services.user_pref_service import UserPrefService

router = APIRouter()


@router.get('/user/preferences')
@router.get('/user/preferences.xml')
@router.get('/user/preferences.json')
async def read_user_preferences(
    _: Annotated[User, api_user(Scope.read_prefs)],
) -> Sequence[dict]:
    prefs = await UserPrefRepository.find_many_by_app(app_id=None)
    return Format06.encode_user_preferences(prefs)


@router.put('/user/preferences')
async def update_user_preferences(
    request: Request,
    _: Annotated[User, api_user(Scope.write_prefs)],
) -> None:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get('preferences', {})

    if not data:
        raise_for().bad_xml(type.value, xml, "XML doesn't contain an osm/preferences element.")

    try:
        prefs = Format06.decode_user_preferences(data.get('preference', ()))
    except Exception as e:
        raise_for().bad_xml(type.value, xml, str(e))

    await UserPrefService.upsert_many(prefs)


@router.get('/user/preferences/{key}')
async def read_user_preference(
    key: Str255,
    _: Annotated[User, api_user(Scope.read_prefs)],
) -> str:
    pref = await UserPrefRepository.find_one_by_app_key(app_id=None, key=key)

    if pref is None:
        raise_for().pref_not_found(app_id=None, key=key)

    return pref.value


@router.put('/user/preferences/{key}')
async def update_user_preference(
    request: Request,
    key: Str255,
    _: Annotated[User, api_user(Scope.write_prefs)],
) -> None:
    value = (await request.body()).decode()
    user_pref = Format06.decode_user_preference({'@k': key, '@v': value})
    await UserPrefService.upsert_one(user_pref)


@router.delete('/user/preferences/{key}')
async def delete_user_preference(
    key: Str255,
    _: Annotated[User, api_user(Scope.write_prefs)],
) -> None:
    await UserPrefService.delete_by_app_key(app_id=None, key=key)
