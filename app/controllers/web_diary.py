from typing import Annotated

from fastapi import APIRouter, Form
from pydantic import PositiveInt
from shapely import Point

from app.lib.auth_context import web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.limits import (
    DIARY_BODY_MAX_LENGTH,
    DIARY_TITLE_MAX_LENGTH,
    LOCALE_CODE_MAX_LENGTH,
)
from app.models.db.user import User
from app.models.geometry import Latitude, Longitude
from app.models.types import LocaleCode
from app.services.diary_service import DiaryService

router = APIRouter(prefix='/api/web/diary')


@router.post('')
async def create_or_update(
    user: Annotated[User, web_user()],
    title: Annotated[str, Form(min_length=1, max_length=DIARY_TITLE_MAX_LENGTH)],
    body: Annotated[str, Form(min_length=1, max_length=DIARY_BODY_MAX_LENGTH)],
    language: Annotated[LocaleCode, Form(min_length=1, max_length=LOCALE_CODE_MAX_LENGTH)],
    lon: Annotated[Longitude | None, Form()] = None,
    lat: Annotated[Latitude | None, Form()] = None,
    diary_id: Annotated[PositiveInt | None, Form()] = None,
):
    lon_provided = lon is not None
    lat_provided = lat is not None
    if lon_provided != lat_provided:
        StandardFeedback.raise_error('lon' if lat_provided else 'lat', t('validation.incomplete_location_information'))
    point = Point(lon, lat) if (lon_provided and lat_provided) else None
    if diary_id is None:
        diary_id = await DiaryService.create(
            title=title,
            body=body,
            language=language,
            point=point,
        )
    else:
        await DiaryService.update(
            diary_id=diary_id,
            title=title,
            body=body,
            language=language,
            point=point,
        )
    return {'redirect_url': f'/user/{user.display_name}/diary/{diary_id}'}


@router.post('/{diary_id:int}/delete')
async def delete(
    user: Annotated[User, web_user()],
    diary_id: PositiveInt,
):
    await DiaryService.delete(diary_id)
    return {'redirect_url': f'/user/{user.display_name}/diary'}
