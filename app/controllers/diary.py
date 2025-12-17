from asyncio import TaskGroup
from typing import Annotated

import cython
from fastapi import APIRouter, Path, Query, Response
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import (
    DIARY_BODY_MAX_LENGTH,
    DIARY_COMMENT_BODY_MAX_LENGTH,
    DIARY_TITLE_MAX_LENGTH,
)
from app.lib.auth_context import auth_user, web_user
from app.lib.locale import (
    INSTALLED_LOCALES_NAMES_MAP,
    LOCALES_NAMES_MAP,
    normalize_locale,
)
from app.lib.render_response import render_response
from app.lib.translation import primary_translation_locale
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.diary import diaries_resolve_rich_text
from app.models.db.user import User, UserDisplay
from app.models.types import DiaryId, LocaleCode
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.user_token_unsubscribe_service import UserTokenUnsubscribeService
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/diary/new')
async def new():
    return await render_response(
        'diary/compose',
        {
            'new': True,
            'LOCALES_NAMES_MAP': LOCALES_NAMES_MAP,
            'DIARY_TITLE_MAX_LENGTH': DIARY_TITLE_MAX_LENGTH,
            'DIARY_BODY_MAX_LENGTH': DIARY_BODY_MAX_LENGTH,
        },
    )


@router.get('/diary/{diary_id:int}')
async def details(
    diary_id: DiaryId,
    *,
    unsubscribe: bool = False,
):
    diary = await DiaryQuery.find_by_id(diary_id)
    if diary is None:
        return await render_response(
            'diary/not-found',
            {'diary_id': diary_id},
            status=status.HTTP_404_NOT_FOUND,
        )

    async with TaskGroup() as tg:
        diaries = [diary]
        tg.create_task(UserQuery.resolve_users(diaries))
        tg.create_task(diaries_resolve_rich_text(diaries))
        tg.create_task(DiaryQuery.resolve_location_name(diaries))
        tg.create_task(DiaryCommentQuery.resolve_num_comments(diaries))
        tg.create_task(UserSubscriptionQuery.resolve_is_subscribed('diary', diaries))

    profile = diary['user']  # type: ignore
    data = _diary_page_meta(profile=profile, language=None)

    return await render_response(
        'diary/details',
        {
            **data,
            'diary': diary,
            'unsubscribe_target': 'diary' if unsubscribe else None,
            'unsubscribe_id': diary_id if unsubscribe else None,
            'LOCALES_NAMES_MAP': LOCALES_NAMES_MAP,
            'DIARY_COMMENT_BODY_MAX_LENGTH': DIARY_COMMENT_BODY_MAX_LENGTH,
        },
    )


@router.get('/diary/{diary_id:int}/unsubscribe')
async def get_unsubscribe(
    _: Annotated[User, web_user()],
    diary_id: DiaryId,
):
    if not await UserSubscriptionQuery.is_subscribed('diary', diary_id):
        return RedirectResponse(f'/diary/{diary_id}', status.HTTP_303_SEE_OTHER)
    return await details(diary_id, unsubscribe=True)


@router.post('/diary/{diary_id:int}/unsubscribe')
async def post_unsubscribe(
    diary_id: DiaryId,
    token: Annotated[SecretStr, Query(min_length=1)],
):
    token_struct = await UserTokenStructUtils.from_str_stateless(token)
    await UserTokenUnsubscribeService.unsubscribe('diary', diary_id, token_struct)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.get('/diary/{diary_id:int}/subscription')
async def legacy_subscription(diary_id: DiaryId):
    return RedirectResponse(f'/diary/{diary_id}/unsubscribe')


@router.get('/diary/{diary_id:int}/edit')
async def edit(
    user: Annotated[User, web_user()],
    diary_id: DiaryId,
):
    diary = await DiaryQuery.find_by_id(diary_id)
    if diary is None or diary['user_id'] != user['id']:
        return render_response(
            'diary/not-found',
            {'diary_id': diary_id},
            status=status.HTTP_404_NOT_FOUND,
        )

    point = diary['point']
    return await render_response(
        'diary/compose',
        {
            'new': False,
            'LOCALES_NAMES_MAP': LOCALES_NAMES_MAP,
            'DIARY_TITLE_MAX_LENGTH': DIARY_TITLE_MAX_LENGTH,
            'DIARY_BODY_MAX_LENGTH': DIARY_BODY_MAX_LENGTH,
            'diary_id': diary_id,
            'title': diary['title'],
            'body': diary['body'],
            'language': diary['language'],
            'lon': round(point.x, 7) if (point is not None) else '',
            'lat': round(point.y, 7) if (point is not None) else '',
        },
    )


@router.get('/diary')
async def index():
    data = await _get_index_data(profile=None, language=None)
    return await render_response('diary/index', data)


@router.get('/diary/{language:str}')
async def language_index(
    language: Annotated[LocaleCode, Path(min_length=1)],
):
    data = await _get_index_data(profile=None, language=language)
    return await render_response('diary/index', data)


@router.get('/user/{display_name:str}/diary')
async def user_index(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    data = await _get_index_data(profile=user, language=None)
    return await render_response('diary/index', data)


@router.get('/user/{_:str}/diary/{diary_id:int}{suffix:path}')
async def legacy_user_diary(_, diary_id: DiaryId, suffix: str):
    return RedirectResponse(
        f'/diary/{diary_id}{suffix}', status.HTTP_301_MOVED_PERMANENTLY
    )


async def _get_index_data(
    *,
    profile: User | UserDisplay | None,
    language: LocaleCode | None,
) -> dict:
    data = _diary_page_meta(profile=profile, language=language)

    pagination_action = '/api/web/diary/page'
    if (profile := data['profile']) is not None:
        pagination_action += f'?user_id={profile["id"]}'
    elif (normalized_language := data['language']) is not None:
        pagination_action += f'?language={normalized_language}'

    data['pagination_action'] = pagination_action
    return data


@cython.cfunc
def _diary_page_meta(
    *,
    profile: User | UserDisplay | None,
    language: LocaleCode | None,
) -> dict:
    primary_locale = primary_translation_locale()
    primary_locale_name = INSTALLED_LOCALES_NAMES_MAP[primary_locale].native

    language = normalize_locale(language)
    if language is not None:
        locale_name = LOCALES_NAMES_MAP[language]
        language_name = (
            locale_name.native if language == primary_locale else locale_name.english
        )
    else:
        language_name = None

    base_url = (
        f'/user/{profile["display_name"]}/diary'  #
        if profile is not None
        else '/diary'
    )
    if language is not None:
        base_url += f'/{language}'

    return {
        'profile': profile,
        'active_tab': _get_active_tab(profile, language, primary_locale),
        'primary_locale': primary_locale,
        'primary_locale_name': primary_locale_name,
        'base_url': base_url,
        'language': language,
        'language_name': language_name,
    }


@cython.cfunc
def _get_active_tab(
    profile: User | UserDisplay | None,
    language: LocaleCode | None,
    primary_locale: LocaleCode,
) -> int:
    """Get the active tab number for the diaries page."""
    if language is not None:
        if language == primary_locale:
            return 1  # viewing own language diaries
        return 2  # viewing other language diaries

    if profile is not None:
        current_user = auth_user()
        if current_user is not None and profile['id'] == current_user['id']:
            return 3  # viewing own diaries
        return 4  # viewing other user's diaries

    return 0  # viewing all diaries
