from asyncio import TaskGroup
from math import ceil
from typing import Annotated

import cython
from fastapi import APIRouter, Path, Query, Response
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import (
    DIARY_BODY_MAX_LENGTH,
    DIARY_COMMENT_BODY_MAX_LENGTH,
    DIARY_COMMENTS_PAGE_SIZE,
    DIARY_LIST_PAGE_SIZE,
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
from app.models.db.diary import Diary, diaries_resolve_rich_text
from app.models.db.user import User, UserDisplay
from app.models.types import DiaryId, DisplayName, LocaleCode
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.user_token_unsubscribe_service import UserTokenUnsubscribeService

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
    async with TaskGroup() as tg:
        is_subscribed_t = tg.create_task(
            UserSubscriptionQuery.is_subscribed('diary', diary_id)
        )

        data = await _get_data(
            user=None,
            language=None,
            after=diary_id - 1,  # type: ignore
            before=diary_id + 1,  # type: ignore
            user_from_diary=True,
            with_navigation=False,
        )
        diaries: list[Diary] = data['diaries']
        if not diaries:
            return await render_response(
                'diary/not-found',
                {'diary_id': diary_id},
                status=status.HTTP_404_NOT_FOUND,
            )
        diary = diaries[0]

    diary_comments_num_items = diary['num_comments']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    diary_comments_num_pages = ceil(diary_comments_num_items / DIARY_COMMENTS_PAGE_SIZE)

    return await render_response(
        'diary/details',
        {
            **data,
            'diary': diary,
            'is_subscribed': is_subscribed_t.result(),
            'diary_comments_num_items': diary_comments_num_items,
            'diary_comments_num_pages': diary_comments_num_pages,
            'DIARY_COMMENT_BODY_MAX_LENGTH': DIARY_COMMENT_BODY_MAX_LENGTH,
            'unsubscribe_target': 'diary' if unsubscribe else None,
            'unsubscribe_id': diary_id if unsubscribe else None,
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
    diary = await DiaryQuery.find_one_by_id(diary_id)
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
            'lon': round(point.x, 5) if (point is not None) else '',
            'lat': round(point.y, 5) if (point is not None) else '',
        },
    )


@router.get('/diary')
async def index(
    after: Annotated[DiaryId | None, Query()] = None,
    before: Annotated[DiaryId | None, Query()] = None,
):
    data = await _get_data(user=None, language=None, after=after, before=before)
    return await render_response('diary/index', data)


@router.get('/diary/{language:str}')
async def language_index(
    language: Annotated[LocaleCode, Path(min_length=1)],
    after: Annotated[DiaryId | None, Query()] = None,
    before: Annotated[DiaryId | None, Query()] = None,
):
    data = await _get_data(user=None, language=language, after=after, before=before)
    return await render_response('diary/index', data)


@router.get('/user/{display_name:str}/diary')
async def user_index(
    display_name: Annotated[DisplayName, Path(min_length=1)],
    after: Annotated[DiaryId | None, Query()] = None,
    before: Annotated[DiaryId | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    data = await _get_data(user=user, language=None, after=after, before=before)
    return await render_response('diary/index', data)


@router.get('/user/{_:str}/diary/{diary_id:int}{suffix:path}')
async def legacy_user_diary(_, diary_id: DiaryId, suffix: str):
    return RedirectResponse(
        f'/diary/{diary_id}{suffix}', status.HTTP_301_MOVED_PERMANENTLY
    )


async def _get_data(
    *,
    user: User | UserDisplay | None,
    language: LocaleCode | None,
    after: DiaryId | None,
    before: DiaryId | None,
    user_from_diary: bool = False,
    with_navigation: bool = True,  # If True, will resolve new_after/new_before fields
) -> dict:
    user_id = user['id'] if user is not None else None
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

    diaries = await DiaryQuery.find_many_recent(
        user_id=user_id,
        language=language,
        after=after,
        before=before,
        limit=DIARY_LIST_PAGE_SIZE,
    )

    async def new_after_task():
        after = diaries[0]['id']
        after_diaries = await DiaryQuery.find_many_recent(
            user_id=user_id,
            language=language,
            after=after,
            limit=1,
        )
        return after if after_diaries else None

    async def new_before_task():
        before = diaries[-1]['id']
        before_diaries = await DiaryQuery.find_many_recent(
            user_id=user_id,
            language=language,
            before=before,
            limit=1,
        )
        return before if before_diaries else None

    new_after_t = None
    new_before_t = None

    if diaries:
        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(diaries))
            tg.create_task(diaries_resolve_rich_text(diaries))
            tg.create_task(DiaryQuery.resolve_location_name(diaries))
            tg.create_task(DiaryCommentQuery.resolve_num_comments(diaries))

            if with_navigation:
                new_after_t = tg.create_task(new_after_task())
                new_before_t = tg.create_task(new_before_task())  # pyright: ignore [reportGeneralTypeIssues]

        if user_from_diary:
            user = diaries[0]['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
            user_id = user['id']

    new_after = new_after_t.result() if new_after_t is not None else None
    new_before = new_before_t.result() if new_before_t is not None else None

    base_url = f'/user/{user["display_name"]}/diary' if user is not None else '/diary'
    if language is not None:
        base_url += f'/{language}'

    active_tab = _get_active_tab(user, language, primary_locale)

    return {
        'profile': user,
        'active_tab': active_tab,
        'primary_locale': primary_locale,
        'primary_locale_name': primary_locale_name,
        'base_url': base_url,
        'language': language,
        'language_name': language_name,
        'new_after': new_after,
        'new_before': new_before,
        'diaries': diaries,
        'LOCALES_NAMES_MAP': LOCALES_NAMES_MAP,
    }


@cython.cfunc
def _get_active_tab(
    user: User | UserDisplay | None,
    language: LocaleCode | None,
    primary_locale: LocaleCode,
) -> int:
    """Get the active tab number for the diaries page."""
    if language is not None:
        if language == primary_locale:
            return 1  # viewing own language diaries
        return 2  # viewing other language diaries

    if user is not None:
        current_user = auth_user()
        if current_user is not None and user['id'] == current_user['id']:
            return 3  # viewing own diaries
        return 4  # viewing other user's diaries

    return 0  # viewing all diaries
